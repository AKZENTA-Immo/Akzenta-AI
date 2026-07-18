from __future__ import annotations

import base64
import binascii
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.agents.manager import AgentManager
from backend.models.agent_models import CrmPreviewRequest, EmailDraftRequest, WorkflowStartRequest
from backend.phone.appointment_manager import AppointmentManager
from backend.phone.call_summary import CallSummary
from backend.phone.conversation_memory import ConversationMemory
from backend.phone.dialog_manager import DialogManager
from backend.rag.knowledge_service import KnowledgeService
from backend.phone.stt_adapter import STTAdapter, UnconfiguredSTTAdapter
from backend.phone.tts_adapter import TTSAdapter, UnconfiguredTTSAdapter


class PhoneSessionNotFound(LookupError): pass
class PhoneSessionClosed(RuntimeError): pass


class PhoneStartRequest(BaseModel):
    phone: str | None = Field(default=None, max_length=50)
    name: str | None = Field(default=None, max_length=100)


class PhoneMessageRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str | None = Field(default=None, min_length=1, max_length=4000)
    audio_base64: str | None = Field(default=None, max_length=15_000_000)
    synthesize_audio: bool = False
    appointment_start: datetime | None = None
    appointment_duration_minutes: int = Field(default=30, ge=15, le=240)

    @field_validator("session_id")
    @classmethod
    def strip_text(cls, value: str) -> str:
        if not value.strip(): raise ValueError("Wert darf nicht leer sein.")
        return value.strip()

    @model_validator(mode="after")
    def require_message_or_audio(self):
        if not ((self.message and self.message.strip()) or self.audio_base64):
            raise ValueError("message oder audio_base64 ist erforderlich.")
        if self.message: self.message = self.message.strip()
        return self


class PhoneEndRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    create_email_draft: bool = False


class CallManager:
    """Coordinates a local call while all infrastructure remains injectable."""

    def __init__(self, memory: ConversationMemory | None = None, knowledge_service: KnowledgeService | None = None,
                 agent_manager: AgentManager | None = None, dialog: DialogManager | None = None,
                 summary_service: CallSummary | None = None, appointment_manager: AppointmentManager | None = None,
                 stt_adapter: STTAdapter | None = None, tts_adapter: TTSAdapter | None = None):
        self.memory = memory or ConversationMemory()
        self.agents = agent_manager or AgentManager()
        self.knowledge_service = knowledge_service or KnowledgeService()
        self.dialog = dialog or DialogManager(self.knowledge_service)
        self.summary_service = summary_service or CallSummary()
        self.appointments = appointment_manager or AppointmentManager(self.memory)
        self.stt = stt_adapter or UnconfiguredSTTAdapter()
        self.tts = tts_adapter or UnconfiguredTTSAdapter()

    def start(self, request: PhoneStartRequest) -> dict[str, Any]:
        session_id = f"ps_{uuid4().hex}"; call_id = f"call_{uuid4().hex}"
        workflow = self.agents.workflow_engine.start_workflow(WorkflowStartRequest(
            definition_id="phone_conversation", requested_by="phone_agent",
            input={"name": request.name or "Telefonkontakt", "appointment_requested": False, "email_followup": False, "handover": False},
            metadata={"session_id": session_id},
        ))
        state = self.memory.create(session_id, call_id, request.phone, workflow.workflow_id)
        if request.name: state["name"] = request.name; self.memory.update(session_id, state)
        greeting = "Guten Tag, hier ist AKZENTA Immobilien. Wie kann ich Ihnen helfen?"
        self.memory.add_message(session_id, "assistant", greeting, "begruessung")
        return {"session_id": session_id, "call_id": call_id, "workflow_id": workflow.workflow_id, "status": "active", "message": greeting, "state": state}

    def _active(self, session_id: str) -> dict[str, Any]:
        session = self.memory.get(session_id)
        if not session: raise PhoneSessionNotFound("Telefonsitzung wurde nicht gefunden.")
        if session["status"] != "active": raise PhoneSessionClosed("Telefonsitzung ist bereits beendet.")
        return session

    def message(self, request: PhoneMessageRequest) -> dict[str, Any]:
        session = self._active(request.session_id)
        text = request.message
        if text is None:
            try: audio = base64.b64decode(request.audio_base64 or "", validate=True)
            except (ValueError, binascii.Error) as exc: raise ValueError("audio_base64 ist ungültig.") from exc
            text = self.stt.transcribe(audio)
            if not text.strip(): raise ValueError("STT lieferte keinen Text.")
        answer, intent, state = self.dialog.respond(session["state"], text, request.appointment_start)
        appointment = None
        if request.appointment_start:
            appointment = self.appointments.book(request.session_id, request.appointment_start, request.appointment_duration_minutes, {"name": state.get("name"), "property": state.get("property")})
            state["appointment"] = appointment
        self.memory.add_message(request.session_id, "user", text, intent.value)
        self.memory.add_message(request.session_id, "assistant", answer, intent.value)
        self.memory.update(request.session_id, state)
        response_audio = base64.b64encode(self.tts.synthesize(answer)).decode("ascii") if request.synthesize_audio else None
        return {"session_id": request.session_id, "intent": intent.value, "transcript": text, "message": answer,
                "audio_base64": response_audio, "state": state, "appointment": appointment, "escalation": state.get("escalation")}

    def end(self, request: PhoneEndRequest) -> dict[str, Any]:
        session = self._active(request.session_id)
        summary = self.summary_service.create(session)
        state = session["state"]
        target_group = "seller" if state.get("interest") == "verkaeufer" else "investor" if state.get("interest") == "kapitalanlage" else "buyer"
        contact = state.get("phone") or state.get("name") or request.session_id
        crm = self.agents.crm.preview(CrmPreviewRequest(contact_reference=contact, target_group=target_group, note=summary["summary"]))
        email = None
        if request.create_email_draft:
            email = self.agents.email.draft(EmailDraftRequest(recipient_name=state.get("name") or "Interessent/in", target_group=target_group,
                purpose="Nachbereitung Ihres Telefonats", facts=summary["next_steps"]))
        workflow = self.agents.workflow_engine.run_until_blocked(session["workflow_id"])
        summary["crm_update"] = crm.model_dump(mode="json")
        summary["email_draft"] = email.model_dump(mode="json") if email else None
        summary["workflow_status"] = workflow.status.value
        self.memory.finish(request.session_id, summary)
        return {"session_id": request.session_id, "status": "completed", "summary": summary, "workflow_id": session["workflow_id"]}

    def session(self, session_id: str) -> dict[str, Any]:
        session = self.memory.get(session_id)
        if not session: raise PhoneSessionNotFound("Telefonsitzung wurde nicht gefunden.")
        return session

    def statistics(self) -> dict[str, int]: return self.memory.statistics()
