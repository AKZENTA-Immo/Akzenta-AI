from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WorkflowStatus(str, Enum):
    CREATED="created"; RUNNING="running"; WAITING_FOR_APPROVAL="waiting_for_approval"; PAUSED="paused"; COMPLETED="completed"; FAILED="failed"; CANCELLED="cancelled"
class AgentState(str, Enum):
    RUNNING="running"; IDLE="idle"; DEGRADED="degraded"; UNAVAILABLE="unavailable"; ERROR="error"
class EventSeverity(str, Enum):
    INFO="info"; WARNING="warning"; ERROR="error"; CRITICAL="critical"

class KnowledgeSourceView(BaseModel):
    document_id: str; filename: str; relative_path: str=""; document_type: str=""; page_or_slide: str|None=None; section: str|None=None; chunk_preview: str=""; relevance_score: float=0; query: str=""; used_at: datetime|None=None
class ConversationMessageView(BaseModel):
    speaker: str; text: str; timestamp: datetime; intent: str|None=None; confidence: float|None=None; knowledge_source: KnowledgeSourceView|None=None
class ConversationOverview(BaseModel):
    session_id: str; status: str; started_at: datetime; ended_at: datetime|None=None; duration_seconds: float=0; name: str|None=None; phone: str|None=None; conversation_type: str="inbound"; intent: str|None=None; confidence: float|None=None; lead_score: float=0; escalation_status: str|None=None; appointment_status: str|None=None; followup_status: str|None=None; summary: str|None=None; next_action: str|None=None; workflow_id: str|None=None; messages: list[ConversationMessageView]=Field(default_factory=list); knowledge_sources: list[KnowledgeSourceView]=Field(default_factory=list)
class WorkflowStepView(BaseModel):
    step_id: str; name: str; status: str; position: int=0; agent: str|None=None; attempt: int=0; max_retries: int=0; error: str|None=None; started_at: datetime|None=None; completed_at: datetime|None=None
class WorkflowOverview(BaseModel):
    workflow_id: str; workflow_type: str; status: str; current_step: str|None=None; previous_step: str|None=None; next_step: str|None=None; started_at: datetime; updated_at: datetime; retry_count: int=0; waiting: bool=False; approval_status: str|None=None; error: str|None=None; session_id: str|None=None; lead_id: str|None=None; steps: list[WorkflowStepView]=Field(default_factory=list)
class LeadOverview(BaseModel):
    lead_id: str; name: str|None=None; phone: str|None=None; email: str|None=None; lead_type: str|None=None; category: str|None=None; budget: str|float|None=None; property: str|None=None; desired_time: str|None=None; lead_score: float=0; status: str="new"; open_items: list[str]=Field(default_factory=list); next_action: str|None=None; last_contact: datetime|None=None; session_id: str|None=None; workflow_id: str|None=None
class AgentStatusView(BaseModel):
    name: str; status: AgentState; checked_at: datetime; message: str; error_details: str|None=None
class DashboardStatistics(BaseModel):
    conversations: int=0; active_conversations: int=0; completed_conversations: int=0; average_duration_seconds: float=0; new_leads: int=0; average_lead_score: float=0; seller_leads: int=0; investment_leads: int=0; appointments: int=0; followups: int=0; escalations: int=0; abandoned_conversations: int=0; knowledge_lookups: int=0; successful_workflows: int=0; failed_workflows: int=0
class DashboardEvent(BaseModel):
    id: str; event_type: str; severity: EventSeverity; title: str; message: str; entity_type: str|None=None; entity_id: str|None=None; metadata: dict[str,Any]=Field(default_factory=dict); created_at: datetime
class DashboardNotification(BaseModel):
    id: str; title: str; message: str; severity: EventSeverity; read: bool=False; created_at: datetime
class DashboardOverview(BaseModel):
    active_conversations: int=0; conversations_today: int=0; open_escalations: int=0; open_appointments: int=0; prepared_followups: int=0; active_workflows: int=0; failed_workflows: int=0; new_leads: int=0; average_lead_score: float=0; agent_statuses: list[AgentStatusView]=Field(default_factory=list); recent_events: list[DashboardEvent]=Field(default_factory=list)
