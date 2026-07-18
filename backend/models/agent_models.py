from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class AgentRole(str, Enum):
    VIEWER = "viewer"
    ADVISOR = "advisor"
    APPROVER = "approver"
    ADMIN = "admin"


class AgentContext(BaseModel):
    actor_id: str = Field(default="local-user", min_length=2, max_length=100)
    role: AgentRole = AgentRole.ADVISOR


class AgentStatus(BaseModel):
    agent: str
    mode: Literal["mock", "draft", "simulation", "connected"]
    provider: str
    provider_connected: bool = False
    external_actions_enabled: bool = False
    prompt_version: str = "v1"
    capabilities: list[str]


class ApprovalState(BaseModel):
    required: bool = True
    approved: bool = False
    approval_id: str = Field(default_factory=lambda: str(uuid4()))
    reason: str


class StructuredAgentResponse(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    agent: str
    status: Literal["draft", "simulation", "blocked"]
    summary: str
    output: dict[str, Any]
    approval: ApprovalState
    external_action_executed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CrmPreviewRequest(BaseModel):
    context: AgentContext = Field(default_factory=AgentContext)
    contact_reference: str = Field(min_length=2, max_length=100)
    target_group: Literal["seller", "buyer", "investor"]
    note: str = Field(min_length=3, max_length=2000)

    @field_validator("contact_reference", "note")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class EmailDraftRequest(BaseModel):
    context: AgentContext = Field(default_factory=AgentContext)
    recipient_name: str = Field(min_length=2, max_length=100)
    target_group: Literal["seller", "buyer", "investor"]
    purpose: str = Field(min_length=3, max_length=500)
    facts: list[str] = Field(default_factory=list, max_length=20)


class CalendarSimulationRequest(BaseModel):
    context: AgentContext = Field(default_factory=AgentContext)
    attendee_name: str = Field(min_length=2, max_length=100)
    purpose: str = Field(min_length=3, max_length=500)
    preferred_start: datetime
    duration_minutes: int = Field(default=30, ge=15, le=240)
    timezone: str = Field(default="Europe/Berlin", pattern=r"^[A-Za-z_]+/[A-Za-z_]+$")


class WorkflowCoreRequest(BaseModel):
    context: AgentContext = Field(default_factory=AgentContext)
    lead_id: str = Field(min_length=2, max_length=100)
    recipient_name: str = Field(min_length=2, max_length=100)
    target_group: Literal["seller", "buyer", "investor"]
    purpose: str = Field(min_length=3, max_length=500)
    preferred_start: datetime | None = None
    simulate_calendar: bool = False
    duration_minutes: int = Field(default=30, ge=15, le=240)
    timezone: str = Field(default="Europe/Berlin", pattern=r"^[A-Za-z_]+/[A-Za-z_]+$")

    @field_validator("lead_id", "recipient_name", "purpose")
    @classmethod
    def strip_workflow_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def require_start_for_calendar_simulation(self):
        if self.simulate_calendar and self.preferred_start is None:
            raise ValueError("preferred_start ist bei aktivierter Kalendersimulation erforderlich.")
        return self


class WorkflowStepResult(BaseModel):
    step: Literal["crm_preview", "email_draft", "calendar_simulation"]
    status: Literal["draft", "simulation", "blocked"]
    summary: str
    output: dict[str, Any]
    external_action_executed: bool = False


class WorkflowCoreResponse(BaseModel):
    workflow_id: str = Field(default_factory=lambda: f"wf_{uuid4().hex}")
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    agent: Literal["workflow_core"] = "workflow_core"
    status: Literal["completed"] = "completed"
    summary: str
    steps: list[WorkflowStepResult]
    external_action_executed: bool = False
    approval_required: bool = True
    approval_status: Literal["pending"] = "pending"
    workflow_fingerprint: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkflowRecord(BaseModel):
    workflow_id: str
    created_at: datetime
    updated_at: datetime
    status: str
    workflow_fingerprint: str
    request_payload: dict[str, Any]
    response_payload: dict[str, Any]
    approval_required: bool
    external_actions_performed: bool = False
    execution_mode: Literal["simulation", "dry_run"] = "simulation"
    executed_at: datetime | None = None

    def public_response(self) -> dict[str, Any]:
        response = dict(self.response_payload)
        response.update({
            "workflow_id": self.workflow_id, "status": self.status,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "approval_required": self.approval_required, "execution_mode": self.execution_mode,
            "external_actions_performed": self.external_actions_performed,
        })
        response.pop("workflow_fingerprint", None)
        return response


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"


class ApprovalCreateRequest(BaseModel):
    workflow_id: str = Field(min_length=1, max_length=100)
    expires_in_minutes: int = Field(default=30, ge=1, le=1440)
    requested_by: str | None = Field(default=None, max_length=100)

    @field_validator("workflow_id")
    @classmethod
    def strip_workflow_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("workflow_id darf nicht leer sein.")
        return value.strip()


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    decided_by: str | None = Field(default=None, max_length=100)
    reason: str | None = Field(default=None, max_length=1000)


class ApprovalRecord(BaseModel):
    approval_id: str
    workflow_id: str
    status: ApprovalStatus
    created_at: datetime
    expires_at: datetime
    requested_by: str | None = None
    decided_at: datetime | None = None
    decided_by: str | None = None
    reason: str | None = None
    executed_at: datetime | None = None
    workflow_fingerprint: str


class ApprovalExecutionResponse(BaseModel):
    approval_id: str
    workflow_id: str
    status: Literal["executed"] = "executed"
    execution_mode: Literal["simulation"] = "simulation"
    executed_steps: list[str]
    external_actions_performed: bool = False
    safe: bool = True
    message: str


class ApprovalStatusResponse(BaseModel):
    enabled: bool = True
    mode: Literal["simulation"] = "simulation"
    persistent: bool = True
    persistence: Literal["sqlite"] = "sqlite"
    external_actions_allowed: bool = False
    audit_enabled: bool = True
    database_configured: bool = True
    supported_statuses: list[ApprovalStatus]
    safety_guards: list[str]


class AuditEvent(BaseModel):
    event_id: str
    entity_type: str
    entity_id: str
    workflow_id: str | None = None
    approval_id: str | None = None
    event_type: str
    previous_status: str | None = None
    new_status: str | None = None
    actor: str | None = None
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class WorkflowStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING = "waiting"
    BLOCKED = "blocked"


class WorkflowCondition(BaseModel):
    type: Literal["always", "input_present", "input_equals", "previous_step_succeeded", "previous_step_output_present"] = "always"
    key: str | None = Field(default=None, max_length=100)
    value: Any = None
    step_id: str | None = Field(default=None, max_length=100)


class WorkflowStepDefinition(BaseModel):
    step_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    agent: str = Field(min_length=1, max_length=100)
    action: str = Field(min_length=1, max_length=100)
    depends_on: list[str] = Field(default_factory=list, max_length=20)
    condition: WorkflowCondition = Field(default_factory=WorkflowCondition)
    requires_approval: bool = False
    max_retries: int = Field(default=0, ge=0, le=5)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("step_id", "name", "agent", "action")
    @classmethod
    def non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Wert darf nicht leer sein.")
        return value


class WorkflowDefinition(BaseModel):
    definition_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    version: str = Field(default="1.0", max_length=30)
    steps: list[WorkflowStepDefinition] = Field(min_length=1, max_length=50)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_graph(self):
        ids = [step.step_id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("Doppelte step_ids sind nicht erlaubt.")
        known = set(ids)
        for step in self.steps:
            if any(dep not in known for dep in step.depends_on):
                raise ValueError("depends_on enthält eine unbekannte step_id.")
        graph = {step.step_id: step.depends_on for step in self.steps}
        visiting: set[str] = set(); visited: set[str] = set()
        def visit(node: str):
            if node in visiting: raise ValueError("Zyklische Workflow-Abhängigkeit.")
            if node in visited: return
            visiting.add(node)
            for dep in graph[node]: visit(dep)
            visiting.remove(node); visited.add(node)
        for node in ids: visit(node)
        return self


class WorkflowStartRequest(BaseModel):
    definition_id: str | None = Field(default=None, min_length=1, max_length=100)
    workflow_type: str | None = Field(default=None, min_length=1, max_length=100)
    input: dict[str, Any] = Field(default_factory=dict)
    requested_by: str | None = Field(default=None, max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def definition_required(self):
        if not (self.definition_id or self.workflow_type):
            raise ValueError("definition_id oder workflow_type ist erforderlich.")
        return self


class WorkflowStepState(BaseModel):
    step_id: str
    status: WorkflowStepStatus
    attempt: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)


class WorkflowInstanceResponse(BaseModel):
    workflow_id: str
    definition_id: str
    name: str
    status: WorkflowStatus
    current_step_id: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    requested_by: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    steps: list[WorkflowStepState] = Field(default_factory=list)
    approval_required: bool = True
    approval_id: str | None = None
    safe: bool = True
    execution_mode: Literal["simulation"] = "simulation"
    external_actions_performed: bool = False


class WorkflowResumeRequest(BaseModel):
    actor: str | None = Field(default=None, max_length=100)
    reason: str | None = Field(default=None, max_length=1000)

class WorkflowRetryRequest(WorkflowResumeRequest):
    step_id: str = Field(min_length=1, max_length=100)

class WorkflowCancelRequest(WorkflowResumeRequest): pass

class WorkflowEngineStatusResponse(BaseModel):
    enabled: bool = True
    persistent: bool = True
    persistence: Literal["sqlite"] = "sqlite"
    simulation_only: bool = True
    external_actions_allowed: bool = False
    supported_workflow_statuses: list[WorkflowStatus]
    supported_step_statuses: list[WorkflowStepStatus]
    retry_enabled: bool = True
    resume_enabled: bool = True
    approval_integration: bool = True
    audit_enabled: bool = True
    safe: bool = True
