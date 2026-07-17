from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


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
