"""Idempotente SQLite-Migrationen für die Conversation Engine."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone


SCHEMA_VERSION = 1


class UnsupportedConversationSchema(RuntimeError):
    pass


def _migration_1(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE conversations (
            id TEXT PRIMARY KEY,
            subject TEXT,
            status TEXT NOT NULL CHECK(status IN ('active','archived')),
            primary_channel TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            archived_at TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE INDEX idx_conversations_status_updated ON conversations(status, updated_at DESC);

        CREATE TABLE participants (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            display_name TEXT,
            phone TEXT,
            mobile TEXT,
            email TEXT,
            crm_id TEXT,
            onoffice_id TEXT,
            normalized_phone TEXT,
            normalized_mobile TEXT,
            normalized_email TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE INDEX idx_participants_conversation ON participants(conversation_id, created_at);
        CREATE INDEX idx_participants_phone ON participants(normalized_phone) WHERE normalized_phone IS NOT NULL;
        CREATE INDEX idx_participants_mobile ON participants(normalized_mobile) WHERE normalized_mobile IS NOT NULL;
        CREATE INDEX idx_participants_email ON participants(normalized_email) WHERE normalized_email IS NOT NULL;
        CREATE INDEX idx_participants_crm ON participants(crm_id) WHERE crm_id IS NOT NULL;
        CREATE INDEX idx_participants_onoffice ON participants(onoffice_id) WHERE onoffice_id IS NOT NULL;

        CREATE TABLE messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            participant_id TEXT REFERENCES participants(id) ON DELETE SET NULL,
            channel TEXT NOT NULL,
            direction TEXT NOT NULL CHECK(direction IN ('inbound','outbound','internal')),
            message_type TEXT NOT NULL,
            content TEXT NOT NULL,
            external_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE INDEX idx_messages_timeline ON messages(conversation_id, created_at, id);
        CREATE UNIQUE INDEX idx_messages_external ON messages(channel, external_id) WHERE external_id IS NOT NULL;

        CREATE TABLE events (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            channel TEXT NOT NULL,
            actor_id TEXT,
            summary TEXT NOT NULL,
            created_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE INDEX idx_events_timeline ON events(conversation_id, created_at, id);

        CREATE TABLE attachments (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            content_type TEXT,
            size_bytes INTEGER CHECK(size_bytes IS NULL OR size_bytes >= 0),
            content_hash TEXT,
            storage_reference TEXT NOT NULL,
            document_id TEXT,
            created_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE UNIQUE INDEX idx_attachments_hash ON attachments(content_hash) WHERE content_hash IS NOT NULL;
        CREATE UNIQUE INDEX idx_attachments_document ON attachments(document_id) WHERE document_id IS NOT NULL;

        CREATE TABLE tags (
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY(conversation_id, name)
        );

        CREATE TABLE message_links (
            id TEXT PRIMARY KEY,
            source_message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            UNIQUE(source_message_id, target_type, target_id, relation_type)
        );
        CREATE INDEX idx_message_links_target ON message_links(target_type, target_id);

        CREATE TABLE conversation_state (
            conversation_id TEXT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
            current_intent TEXT,
            assigned_agent TEXT,
            workflow_id TEXT,
            crm_lead_id TEXT,
            state_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL
        );
        CREATE INDEX idx_conversation_state_workflow ON conversation_state(workflow_id) WHERE workflow_id IS NOT NULL;
        CREATE INDEX idx_conversation_state_crm ON conversation_state(crm_lead_id) WHERE crm_lead_id IS NOT NULL;

        CREATE TABLE conversation_memory (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            memory_type TEXT NOT NULL,
            content TEXT NOT NULL,
            importance REAL NOT NULL CHECK(importance >= 0 AND importance <= 1),
            source_message_id TEXT REFERENCES messages(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE INDEX idx_memory_conversation ON conversation_memory(conversation_id, importance DESC, created_at DESC);
        """
    )


MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {1: _migration_1}


def migrate(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS conversation_schema_version "
        "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    row = connection.execute("SELECT MAX(version) FROM conversation_schema_version").fetchone()
    current = int(row[0]) if row and row[0] is not None else 0
    if current > SCHEMA_VERSION:
        raise UnsupportedConversationSchema(
            "Die Conversation-Datenbank verwendet eine neuere, nicht unterstützte Schema-Version."
        )
    for version in range(current + 1, SCHEMA_VERSION + 1):
        MIGRATIONS[version](connection)
        connection.execute(
            "INSERT INTO conversation_schema_version(version, applied_at) VALUES (?, ?)",
            (version, datetime.now(timezone.utc).isoformat()),
        )
