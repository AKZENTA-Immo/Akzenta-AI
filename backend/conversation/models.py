"""Domänenmodelle der kanalübergreifenden Conversation Engine."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class Channel(StrEnum):
    PHONE = "phone"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEBCHAT = "webchat"
    CRM = "crm"
    WORKFLOW = "workflow"
    DASHBOARD = "dashboard"
    RAG = "rag"


class MessageDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INTERNAL = "internal"


class Conversation(BaseModel):
    id: str
    subject: str | None = None
    status: ConversationStatus = ConversationStatus.ACTIVE
    primary_channel: Channel | None = None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Participant(BaseModel):
    id: str
    conversation_id: str
    kind: str = "person"
    display_name: str | None = None
    phone: str | None = None
    mobile: str | None = None
    email: str | None = None
    crm_id: str | None = None
    onoffice_id: str | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    id: str
    conversation_id: str
    participant_id: str | None = None
    channel: Channel
    direction: MessageDirection
    message_type: str = "text"
    content: str
    external_id: str | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationEvent(BaseModel):
    id: str
    conversation_id: str
    event_type: str
    channel: Channel
    actor_id: str | None = None
    summary: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class Attachment(BaseModel):
    id: str
    filename: str
    content_type: str | None = None
    size_bytes: int | None = None
    content_hash: str | None = None
    storage_reference: str
    document_id: str | None = None
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationTag(BaseModel):
    conversation_id: str
    name: str
    created_at: datetime


class MessageLink(BaseModel):
    id: str
    source_message_id: str
    target_type: str
    target_id: str
    relation_type: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationState(BaseModel):
    conversation_id: str
    current_intent: str | None = None
    assigned_agent: str | None = None
    workflow_id: str | None = None
    crm_lead_id: str | None = None
    state: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime


class ConversationMemory(BaseModel):
    id: str
    conversation_id: str
    memory_type: str
    content: str
    importance: float = 0.5
    source_message_id: str | None = None
    created_at: datetime
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
