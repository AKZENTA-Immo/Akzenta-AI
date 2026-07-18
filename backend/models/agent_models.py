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
    persistent: bool = False
    external_actions_allowed: bool = False
    supported_statuses: list[ApprovalStatus]
    safety_guards: list[str]
