from datetime import timedelta

from backend.adapters.providers import CalendarAdapter, GmailAdapter, OnOfficeAdapter
from backend.agents.core import AuditLogger, PromptLoader, require_role, safe_facts
from backend.models.agent_models import (
    AgentRole, AgentStatus, ApprovalState, CalendarSimulationRequest, CrmPreviewRequest,
    EmailDraftRequest, StructuredAgentResponse,
)


class BaseAgentService:
    agent_name = "base"
    prompt_name = "base"
    mode = "mock"
    capabilities: list[str] = []

    def __init__(self, adapter):
        self.adapter = adapter
        self.audit = AuditLogger()
        self.system_prompt = PromptLoader.load(self.prompt_name)

    def status(self) -> AgentStatus:
        provider = self.adapter.status()
        return AgentStatus(agent=self.agent_name, mode=self.mode, provider=provider.name, provider_connected=provider.connected, external_actions_enabled=False, capabilities=self.capabilities)

    def _finish(self, response, context, action):
        self.audit.record(agent=self.agent_name, action=action, context=context, request_id=response.request_id, result=response.status)
        return response


class CrmAgentService(BaseAgentService):
    agent_name, prompt_name, mode = "crm", "crm", "mock"
    capabilities = ["status", "change_preview", "approval_request"]

    def __init__(self, adapter: OnOfficeAdapter): super().__init__(adapter)

    def preview(self, request: CrmPreviewRequest) -> StructuredAgentResponse:
        require_role(request.context, {AgentRole.ADVISOR, AgentRole.APPROVER, AgentRole.ADMIN})
        response = StructuredAgentResponse(agent="crm", status="blocked", summary="CRM-Änderung wurde nur als Vorschau erstellt.", output={
            "operation": "append_note",
            "data_source": "simulation",
            "read_only": True,
            "facts_from_onoffice": [],
            "input_information": {"contact_reference": request.contact_reference, "target_group": request.target_group},
            "proposed_changes": {"note": request.note},
            "missing_information": [],
            "contact_reference": request.contact_reference,
            "target_group": request.target_group,
            "note_preview": request.note,
        }, approval=ApprovalState(reason="onOffice-Schreibzugriff ist gesperrt; menschliche Freigabe bleibt erforderlich."))
        return self._finish(response, request.context, "change_preview")


class EmailAgentService(BaseAgentService):
    agent_name, prompt_name, mode = "email", "email", "draft"
    capabilities = ["status", "draft"]

    def __init__(self, adapter: GmailAdapter): super().__init__(adapter)

    def draft(self, request: EmailDraftRequest) -> StructuredAgentResponse:
        require_role(request.context, {AgentRole.ADVISOR, AgentRole.APPROVER, AgentRole.ADMIN})
        facts = safe_facts(request.facts)
        body = f"Guten Tag {request.recipient_name},\n\n{request.purpose.strip()}"
        if facts: body += "\n\n" + "\n".join(f"- {fact}" for fact in facts)
        body += "\n\nFreundliche Grüße\nAKZENTA Immobilien"
        response = StructuredAgentResponse(agent="email", status="draft", summary="E-Mail-Entwurf erstellt; es wurde nichts versendet.", output={"subject": f"AKZENTA Immobilien – {request.purpose.strip()[:80]}", "body": body, "target_group": request.target_group}, approval=ApprovalState(reason="Versand ist in Phase 1 deaktiviert."))
        return self._finish(response, request.context, "draft")


class CalendarAgentService(BaseAgentService):
    agent_name, prompt_name, mode = "calendar", "calendar", "simulation"
    capabilities = ["status", "appointment_simulation"]

    def __init__(self, adapter: CalendarAdapter): super().__init__(adapter)

    def simulate(self, request: CalendarSimulationRequest) -> StructuredAgentResponse:
        require_role(request.context, {AgentRole.ADVISOR, AgentRole.APPROVER, AgentRole.ADMIN})
        end = request.preferred_start + timedelta(minutes=request.duration_minutes)
        response = StructuredAgentResponse(agent="calendar", status="simulation", summary="Terminvorschlag simuliert; kein Kalender wurde verändert.", output={"title": request.purpose.strip(), "attendee_name": request.attendee_name, "start": request.preferred_start.isoformat(), "end": end.isoformat(), "timezone": request.timezone, "availability_checked": False}, approval=ApprovalState(reason="Kalenderzugang, Verfügbarkeitsprüfung und menschliche Freigabe sind erforderlich."))
        return self._finish(response, request.context, "appointment_simulation")
