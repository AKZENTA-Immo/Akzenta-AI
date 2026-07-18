"""Persistent, allowlisted, simulation-only multi-step workflow orchestration."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from backend.models.agent_models import (
    ApprovalStatus, WorkflowDefinition, WorkflowEngineStatusResponse, WorkflowInstanceResponse,
    WorkflowStartRequest, WorkflowStatus, WorkflowStepDefinition, WorkflowStepState, WorkflowStepStatus,
)
from backend.agents.workflow_repository import ConcurrentUpdateError, WorkflowRepository


class WorkflowDefinitionNotFound(LookupError): pass
class WorkflowInstanceNotFound(LookupError): pass
class WorkflowAlreadyCompleted(RuntimeError): pass
class WorkflowCancelled(RuntimeError): pass
class WorkflowInvalidState(RuntimeError): pass
class WorkflowStepNotFound(LookupError): pass
class WorkflowStepInvalidState(RuntimeError): pass
class WorkflowStepFailed(RuntimeError): pass
class WorkflowRetryLimitReached(RuntimeError): pass
class WorkflowDependencyError(ValueError): pass
class WorkflowConditionError(ValueError): pass
class WorkflowApprovalRequired(PermissionError): pass
class WorkflowApprovalRejected(PermissionError): pass
class WorkflowApprovalExpired(RuntimeError): pass
class WorkflowPersistenceError(RuntimeError): pass


def _step(step_id, agent, action, previous=None, condition=None, approval=False, retries=1):
    return WorkflowStepDefinition(step_id=step_id, name=step_id.replace("_", " ").title(), agent=agent, action=action,
        depends_on=[previous] if previous else [], condition=condition or {"type": "always"}, requires_approval=approval, max_retries=retries)


WORKFLOW_DEFINITIONS = {
    "lead_qualification": WorkflowDefinition(definition_id="lead_qualification", name="Lead-Qualifizierung",
        description="Sichere mehrstufige Qualifizierung mit Freigabe-Gate.", version="1.8", steps=[
            _step("validate_lead", "workflow", "validate_lead", retries=2),
            _step("crm_lookup", "crm", "simulated_read", "validate_lead"),
            _step("document_check", "documents", "simulated_check", "crm_lookup", {"type":"input_present","key":"object_address"}),
            _step("email_draft", "email", "draft", "document_check"),
            _step("calendar_preview", "calendar", "preview", "email_draft", {"type":"input_equals","key":"appointment_requested","value":True}),
            _step("approval_gate", "approval", "request", "calendar_preview", approval=True),
            _step("simulated_execution", "workflow", "simulate_execution", "approval_gate"),
            _step("finalize", "workflow", "finalize", "simulated_execution"),
        ]),
    "seller_follow_up": WorkflowDefinition(definition_id="seller_follow_up", name="Verkäufer-Follow-up",
        description="Sichere simulierte Verkäufer-Nachverfolgung.", version="1.8", steps=[
            _step("validate_request", "workflow", "validate_request", retries=2),
            _step("crm_lookup", "crm", "simulated_read", "validate_request"),
            _step("market_context_preview", "marketing", "market_preview", "crm_lookup"),
            _step("email_draft", "email", "draft", "market_context_preview"),
            _step("approval_gate", "approval", "request", "email_draft", approval=True),
            _step("simulated_execution", "workflow", "simulate_execution", "approval_gate"),
            _step("finalize", "workflow", "finalize", "simulated_execution"),
        ]),
}


class WorkflowOrchestrator:
    ACTION_ALLOWLIST = {step.action for definition in WORKFLOW_DEFINITIONS.values() for step in definition.steps}

    def __init__(self, repository: WorkflowRepository, approvals):
        self.repository, self.approvals = repository, approvals
        for definition in WORKFLOW_DEFINITIONS.values(): self.repository.save_workflow_definition(definition)

    def get_status(self):
        return WorkflowEngineStatusResponse(supported_workflow_statuses=list(WorkflowStatus), supported_step_statuses=list(WorkflowStepStatus))

    def list_definitions(self): return [WorkflowDefinition.model_validate(v) for v in self.repository.list_workflow_definitions()]
    def get_definition(self, definition_id):
        value = self.repository.get_workflow_definition(definition_id)
        if not value: raise WorkflowDefinitionNotFound("Workflow-Definition wurde nicht gefunden.")
        return WorkflowDefinition.model_validate(value)

    def _audit(self, workflow_id, event, previous=None, new=None, actor=None, message=None, metadata=None, approval_id=None):
        self.repository.append_audit_event(entity_type="workflow", entity_id=workflow_id, workflow_id=workflow_id,
            approval_id=approval_id, event_type=event, previous_status=previous, new_status=new, actor=actor,
            message=message, metadata=metadata or {})

    def start_workflow(self, request: WorkflowStartRequest):
        definition = self.get_definition(request.definition_id or request.workflow_type)
        if not definition.enabled: raise WorkflowInvalidState("Workflow-Definition ist deaktiviert.")
        now = datetime.now(timezone.utc).isoformat(); workflow_id = f"wfi_{uuid4().hex}"
        instance = {"workflow_id": workflow_id, "definition_id": definition.definition_id, "name": definition.name,
            "status":"created", "created_at":now, "requested_by":request.requested_by, "input":request.input, "metadata":request.metadata}
        steps = [{**s.model_dump(mode="json"), "position": pos} for pos, s in enumerate(definition.steps)]
        fingerprint = hashlib.sha256(json.dumps(instance, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        self.repository.create_workflow_instance(instance, steps, fingerprint)
        self._audit(workflow_id, "workflow_definition_loaded", new="created", metadata={"definition_id":definition.definition_id})
        return self.get_workflow(workflow_id)

    def get_workflow(self, workflow_id):
        instance = self.repository.get_workflow_instance(workflow_id)
        if not instance: raise WorkflowInstanceNotFound("Workflow-Instanz wurde nicht gefunden.")
        steps = [WorkflowStepState.model_validate({k:s.get(k) for k in WorkflowStepState.model_fields}) for s in self.repository.get_workflow_steps(workflow_id)]
        return WorkflowInstanceResponse(**instance, steps=steps, approval_required=True, safe=True)

    def list_workflows(self, limit=50, status=None): return [self.get_workflow(v["workflow_id"]) for v in self.repository.list_workflow_instances(limit, status)]

    def evaluate_step_condition(self, workflow, step):
        condition = step["condition"]; kind = condition.get("type", "always")
        if kind == "always": return True
        if kind == "input_present": return condition.get("key") in workflow["input"] and workflow["input"].get(condition.get("key")) not in (None, "", [])
        if kind == "input_equals": return workflow["input"].get(condition.get("key")) == condition.get("value")
        previous = self.repository.get_workflow_step(workflow["workflow_id"], condition.get("step_id", ""))
        if kind == "previous_step_succeeded": return bool(previous and previous["status"] == "completed")
        if kind == "previous_step_output_present": return bool(previous and previous["output"].get(condition.get("key")))
        raise WorkflowConditionError("Nicht unterstützter Bedingungstyp.")

    def determine_next_step(self, workflow_id):
        for step in self.repository.get_workflow_steps(workflow_id):
            if step["status"] in ("pending", "blocked"):
                dependencies = [self.repository.get_workflow_step(workflow_id, dep) for dep in step["depends_on"]]
                if all(dep and dep["status"] in ("completed", "skipped") for dep in dependencies): return step
        return None

    def execute_step_simulation(self, workflow, step):
        if step["action"] not in self.ACTION_ALLOWLIST: raise WorkflowStepFailed("Aktion ist nicht registriert.")
        data = workflow["input"]
        if step["action"] in ("validate_lead", "validate_request") and not data.get("name"):
            raise WorkflowStepFailed("Pflichtinformation 'name' fehlt.")
        result = {"agent":step["agent"], "action":step["action"], "status":"simulated", "simulation":True,
            "safe":True, "external_actions_performed":False, "result":{"prepared":True}, "warnings":[], "missing_information":[]}
        if step["action"] == "draft" and not data.get("email"): result["warnings"].append("Keine E-Mail-Adresse; Entwurf bleibt unadressiert.")
        return result

    def run_next_step(self, workflow_id):
        workflow = self.repository.get_workflow_instance(workflow_id)
        if not workflow: raise WorkflowInstanceNotFound("Workflow-Instanz wurde nicht gefunden.")
        if workflow["status"] == "completed": raise WorkflowAlreadyCompleted("Workflow ist bereits abgeschlossen.")
        if workflow["status"] == "cancelled": raise WorkflowCancelled("Abgebrochener Workflow kann nicht fortgesetzt werden.")
        if workflow["status"] == "waiting_for_approval": raise WorkflowApprovalRequired("Freigabe ist erforderlich.")
        step = self.determine_next_step(workflow_id)
        if not step: self.repository.mark_workflow_completed(workflow_id); self._audit(workflow_id,"workflow_completed",new="completed"); return self.get_workflow(workflow_id)
        if not self.evaluate_step_condition(workflow, step):
            self.repository.update_step_status(workflow_id, step["step_id"], "skipped", expected=(step["status"],))
            self._audit(workflow_id,"workflow_step_skipped",metadata={"step_id":step["step_id"]}); return self.get_workflow(workflow_id)
        try: self.repository.update_step_status(workflow_id, step["step_id"], "running", expected=(step["status"],), increment_attempt=True)
        except ConcurrentUpdateError as exc: raise WorkflowStepInvalidState("Schritt wird bereits ausgeführt.") from exc
        self.repository.update_engine_workflow(workflow_id,"running",step["step_id"]); self._audit(workflow_id,"workflow_step_started",metadata={"step_id":step["step_id"]})
        if step["action"] == "request":
            approval = self.approvals.create_approval(workflow_id, requested_by=workflow.get("requested_by"))
            self.repository.update_step_status(workflow_id, step["step_id"], "waiting", expected=("running",))
            self.repository.set_workflow_approval(workflow_id, approval.approval_id)
            self._audit(workflow_id,"workflow_waiting_for_approval",new="waiting_for_approval",approval_id=approval.approval_id)
            return self.get_workflow(workflow_id)
        try:
            output = self.execute_step_simulation(workflow, step)
            self.repository.update_step_status(workflow_id, step["step_id"], "completed", output=output, expected=("running",))
            self._audit(workflow_id,"workflow_step_completed",metadata={"step_id":step["step_id"]})
        except WorkflowStepFailed as exc:
            self.repository.update_step_status(workflow_id, step["step_id"], "failed", error=str(exc), expected=("running",))
            self.repository.update_engine_workflow(workflow_id,"failed",step["step_id"]); self._audit(workflow_id,"workflow_step_failed",new="failed",message=str(exc),metadata={"step_id":step["step_id"]})
        return self.get_workflow(workflow_id)

    def run_until_blocked(self, workflow_id):
        self._audit(workflow_id,"workflow_started",new="running")
        for _ in range(100):
            result = self.run_next_step(workflow_id)
            if result.status in {WorkflowStatus.WAITING_FOR_APPROVAL, WorkflowStatus.FAILED, WorkflowStatus.PAUSED, WorkflowStatus.COMPLETED, WorkflowStatus.CANCELLED}: return result
        raise WorkflowInvalidState("Workflow-Schrittlimit überschritten.")

    def resume_workflow(self, workflow_id, actor=None, reason=None):
        workflow = self.repository.get_workflow_instance(workflow_id)
        if not workflow: raise WorkflowInstanceNotFound("Workflow-Instanz wurde nicht gefunden.")
        if workflow["status"] == "cancelled": raise WorkflowCancelled("Abgebrochener Workflow kann nicht fortgesetzt werden.")
        if workflow["status"] == "completed": raise WorkflowAlreadyCompleted("Workflow ist bereits abgeschlossen.")
        if workflow["status"] not in ("paused","failed","waiting_for_approval"): raise WorkflowInvalidState("Workflow kann in diesem Zustand nicht fortgesetzt werden.")
        if workflow["status"] == "waiting_for_approval":
            approval = self.approvals.get_approval(workflow["approval_id"])
            if approval.status == ApprovalStatus.PENDING: raise WorkflowApprovalRequired("Freigabe ist noch ausstehend.")
            if approval.status == ApprovalStatus.REJECTED: raise WorkflowApprovalRejected("Freigabe wurde abgelehnt.")
            if approval.status == ApprovalStatus.EXPIRED: raise WorkflowApprovalExpired("Freigabe ist abgelaufen.")
            if approval.workflow_fingerprint != self.repository.get_workflow(workflow_id).workflow_fingerprint: raise WorkflowInvalidState("Workflow-Integritätsprüfung fehlgeschlagen.")
            gate = next(s for s in self.repository.get_workflow_steps(workflow_id) if s["status"] == "waiting")
            self.repository.update_step_status(workflow_id,gate["step_id"],"completed",output={"approved":True,"simulation":True,"external_actions_performed":False},expected=("waiting",))
        self.repository.update_engine_workflow(workflow_id,"running"); self._audit(workflow_id,"workflow_resumed",new="running",actor=actor,message=reason)
        return self.run_until_blocked(workflow_id)

    def retry_step(self, workflow_id, step_id, actor=None, reason=None):
        step = self.repository.get_workflow_step(workflow_id,step_id)
        if not step: raise WorkflowStepNotFound("Workflow-Schritt wurde nicht gefunden.")
        if step["status"] != "failed": raise WorkflowStepInvalidState("Nur fehlgeschlagene Schritte können erneut versucht werden.")
        if step["attempt"] > step["max_retries"]:
            self._audit(workflow_id,"workflow_retry_limit_reached",metadata={"step_id":step_id}); raise WorkflowRetryLimitReached("Retry-Limit wurde erreicht.")
        self.repository.update_step_status(workflow_id,step_id,"pending",error=None,expected=("failed",))
        self.repository.update_engine_workflow(workflow_id,"paused",step_id); self._audit(workflow_id,"workflow_retry_requested",actor=actor,message=reason,metadata={"step_id":step_id})
        return self.resume_workflow(workflow_id,actor,reason)

    def cancel_workflow(self, workflow_id, actor=None, reason=None):
        workflow = self.repository.get_workflow_instance(workflow_id)
        if not workflow: raise WorkflowInstanceNotFound("Workflow-Instanz wurde nicht gefunden.")
        if workflow["status"] == "completed": raise WorkflowAlreadyCompleted("Workflow ist bereits abgeschlossen.")
        self.repository.cancel_workflow(workflow_id); self._audit(workflow_id,"workflow_cancelled",new="cancelled",actor=actor,message=reason)
        return self.get_workflow(workflow_id)
