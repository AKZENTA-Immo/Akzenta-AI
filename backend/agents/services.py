import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.adapters.providers import CalendarAdapter, GmailAdapter, OnOfficeAdapter
from backend.agents.core import AuditLogger, PromptLoader, require_role, safe_facts
from backend.agents.workflow_repository import ConcurrentUpdateError, WorkflowRepository
from backend.models.agent_models import (
    AgentRole, AgentStatus, ApprovalExecutionResponse, ApprovalRecord, ApprovalState,
    ApprovalStatus, ApprovalStatusResponse, CalendarSimulationRequest, CrmPreviewRequest,
    EmailDraftRequest, StructuredAgentResponse, WorkflowCoreRequest, WorkflowCoreResponse,
    WorkflowStepResult,
)


class WorkflowNotFound(LookupError): pass
class ApprovalNotFound(LookupError): pass
class ApprovalConflict(RuntimeError): pass
class ApprovalExpired(RuntimeError): pass
class ApprovalNotApproved(PermissionError): pass
class ApprovalAlreadyExecuted(RuntimeError): pass
class WorkflowIntegrityError(RuntimeError): pass


class ApprovalService:
    """Persistent approval rules. All executions remain simulations only."""

    def __init__(self, repository: WorkflowRepository, now=None):
        self.repository = repository
        self._now = now or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _fingerprint(workflow: WorkflowCoreResponse) -> str:
        payload = {
            "workflow_id": workflow.workflow_id,
            "steps": [step.model_dump(mode="json") for step in workflow.steps],
            "external_action_executed": workflow.external_action_executed,
            "approval_required": workflow.approval_required,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def get_status(self) -> ApprovalStatusResponse:
        return ApprovalStatusResponse(
            supported_statuses=list(ApprovalStatus),
            safety_guards=["approval_required", "expiry_check", "single_execution", "workflow_fingerprint", "simulation_only"],
        )

    def register_workflow(self, request: WorkflowCoreRequest, workflow: WorkflowCoreResponse) -> WorkflowCoreResponse:
        workflow.workflow_fingerprint = self._fingerprint(workflow)
        self.repository.save_workflow(request.model_dump(mode="json"), workflow)
        return workflow

    def _refresh_expiry(self, approval: ApprovalRecord) -> ApprovalRecord:
        return self.repository.expire_approval(approval.approval_id, self._now()) or approval

    def _blocked(self, approval: ApprovalRecord, message: str) -> None:
        self.repository.add_audit_event(
            entity_type="approval", entity_id=approval.approval_id, workflow_id=approval.workflow_id,
            approval_id=approval.approval_id, event_type="execution_blocked",
            previous_status=approval.status.value, new_status=approval.status.value, message=message,
        )

    def create_approval(self, workflow_id: str, expires_in_minutes: int = 30, requested_by: str | None = None) -> ApprovalRecord:
        workflow = self.repository.get_workflow(workflow_id)
        if workflow is None:
            raise WorkflowNotFound("Workflow wurde nicht gefunden.")
        pending = self.repository.get_pending_approval_for_workflow(workflow_id)
        if pending:
            pending = self._refresh_expiry(pending)
            if pending.status == ApprovalStatus.PENDING and pending.workflow_fingerprint == workflow.workflow_fingerprint:
                return pending
        now = self._now()
        return self.repository.save_approval(ApprovalRecord(
            approval_id=f"apr_{uuid4().hex}", workflow_id=workflow_id, status=ApprovalStatus.PENDING,
            created_at=now, expires_at=now + timedelta(minutes=expires_in_minutes),
            requested_by=requested_by, workflow_fingerprint=workflow.workflow_fingerprint,
        ))

    def get_approval(self, approval_id: str) -> ApprovalRecord:
        approval = self.repository.get_approval(approval_id)
        if approval is None:
            raise ApprovalNotFound("Freigabe wurde nicht gefunden.")
        return self._refresh_expiry(approval)

    def decide_approval(self, approval_id: str, decision: str, decided_by: str | None = None, reason: str | None = None) -> ApprovalRecord:
        approval = self.get_approval(approval_id)
        if approval.status == ApprovalStatus.EXPIRED:
            raise ApprovalExpired("Freigabe ist abgelaufen.")
        if approval.status != ApprovalStatus.PENDING:
            raise ApprovalConflict("Nur eine ausstehende Freigabe kann entschieden werden.")
        try:
            return self.repository.update_approval_decision(approval_id, ApprovalStatus(decision), self._now(), decided_by, reason)
        except ConcurrentUpdateError as exc:
            raise ApprovalConflict("Freigabestatus wurde zwischenzeitlich geändert.") from exc

    def execute_approved_workflow(self, approval_id: str) -> ApprovalExecutionResponse:
        approval = self.get_approval(approval_id)
        if approval.status == ApprovalStatus.EXPIRED:
            self._blocked(approval, "Freigabe ist abgelaufen.")
            raise ApprovalExpired("Freigabe ist abgelaufen.")
        if approval.status == ApprovalStatus.EXECUTED:
            self._blocked(approval, "Freigabe wurde bereits ausgeführt.")
            raise ApprovalAlreadyExecuted("Freigabe wurde bereits ausgeführt.")
        if approval.status != ApprovalStatus.APPROVED:
            self._blocked(approval, "Workflow ist nicht freigegeben.")
            raise ApprovalNotApproved("Workflow ist nicht freigegeben.")
        stored = self.repository.get_workflow(approval.workflow_id)
        if stored is None:
            raise WorkflowNotFound("Workflow wurde nicht gefunden.")
        workflow = WorkflowCoreResponse.model_validate(stored.response_payload)
        calculated = self._fingerprint(workflow)
        try:
            updated = self.repository.mark_approval_executed(approval_id, approval.workflow_fingerprint, calculated, self._now())
        except ConcurrentUpdateError as exc:
            raise ApprovalAlreadyExecuted("Freigabe wurde bereits ausgeführt.") from exc
        if updated.status != ApprovalStatus.EXECUTED:
            raise WorkflowIntegrityError("Workflow-Integritätsprüfung fehlgeschlagen.")
        return ApprovalExecutionResponse(
            approval_id=approval.approval_id, workflow_id=workflow.workflow_id,
            executed_steps=[step.step for step in workflow.steps],
            message="Freigegebener Workflow wurde ausschließlich lokal simuliert; keine externe Aktion wurde ausgeführt.",
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


class WorkflowCoreService:
    agent_name = "workflow_core"

    def __init__(self, crm: CrmAgentService, email: EmailAgentService, calendar: CalendarAgentService, approvals: ApprovalService):
        self.crm = crm
        self.email = email
        self.calendar = calendar
        self.approvals = approvals
        self.audit = AuditLogger()

    def status(self) -> AgentStatus:
        return AgentStatus(
            agent=self.agent_name,
            mode="simulation",
            provider="internal",
            provider_connected=False,
            external_actions_enabled=False,
            capabilities=["status", "crm_preview", "email_draft", "optional_calendar_simulation"],
        )

    @staticmethod
    def _step(name: str, response: StructuredAgentResponse) -> WorkflowStepResult:
        return WorkflowStepResult(
            step=name,
            status=response.status,
            summary=response.summary,
            output=response.output,
            external_action_executed=response.external_action_executed,
        )

    def run(self, request: WorkflowCoreRequest) -> WorkflowCoreResponse:
        require_role(request.context, {AgentRole.ADVISOR, AgentRole.APPROVER, AgentRole.ADMIN})
        crm_response = self.crm.preview(CrmPreviewRequest(
            context=request.context,
            contact_reference=request.lead_id,
            target_group=request.target_group,
            note=f"Workflow-Vorschau: {request.purpose}",
        ))
        email_response = self.email.draft(EmailDraftRequest(
            context=request.context,
            recipient_name=request.recipient_name,
            target_group=request.target_group,
            purpose=request.purpose,
            facts=[f"Lead-Referenz: {request.lead_id}"],
        ))
        steps = [self._step("crm_preview", crm_response), self._step("email_draft", email_response)]

        if request.simulate_calendar:
            calendar_response = self.calendar.simulate(CalendarSimulationRequest(
                context=request.context,
                attendee_name=request.recipient_name,
                purpose=request.purpose,
                preferred_start=request.preferred_start,
                duration_minutes=request.duration_minutes,
                timezone=request.timezone,
            ))
            steps.append(self._step("calendar_simulation", calendar_response))

        response = WorkflowCoreResponse(
            summary="Workflow sicher ausgeführt; es wurden nur Vorschau, Entwurf und Simulation erzeugt.",
            steps=steps,
        )
        self.audit.record(
            agent=self.agent_name,
            action="core_run",
            context=request.context,
            request_id=response.request_id,
            result=response.status,
        )
        return self.approvals.register_workflow(request, response)
