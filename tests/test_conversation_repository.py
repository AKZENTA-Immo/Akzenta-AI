import sqlite3
from datetime import datetime, timezone

import pytest

from backend.conversation.migrations import SCHEMA_VERSION, UnsupportedConversationSchema
from backend.conversation.models import Channel, Conversation, ConversationEvent, Message, MessageDirection, Participant
from backend.conversation.repository import ConversationRepository


NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


def conversation() -> Conversation:
    return Conversation(id="conv_1", subject="Wohnung Hamburg", primary_channel=Channel.PHONE, created_at=NOW, updated_at=NOW)


def test_migration_creates_all_required_tables_and_is_idempotent(tmp_path):
    path = tmp_path / "conversation.sqlite3"
    ConversationRepository(path)
    ConversationRepository(path)
    with sqlite3.connect(path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        version = connection.execute("SELECT MAX(version) FROM conversation_schema_version").fetchone()[0]
    assert {"conversations", "participants", "messages", "events", "attachments", "tags", "message_links", "conversation_state", "conversation_memory"} <= tables
    assert version == SCHEMA_VERSION


def test_unknown_newer_schema_is_rejected(tmp_path):
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE conversation_schema_version(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        connection.execute("INSERT INTO conversation_schema_version VALUES (999, ?)", (NOW.isoformat(),))
    with pytest.raises(UnsupportedConversationSchema):
        ConversationRepository(path)


def test_repository_persists_conversation_participant_message_and_event(tmp_path):
    repository = ConversationRepository(tmp_path / "conversation.sqlite3")
    created = repository.create_conversation(conversation())
    participant = Participant(id="part_1", conversation_id=created.id, display_name="Ada", phone="040 123", created_at=NOW, updated_at=NOW)
    repository.add_participant(participant, normalized_phone="+4940123")
    message = Message(id="msg_1", conversation_id=created.id, participant_id=participant.id, channel=Channel.PHONE,
                      direction=MessageDirection.INBOUND, content="Ich suche eine Wohnung", created_at=NOW, updated_at=NOW)
    repository.add_message(message)
    event = ConversationEvent(id="evt_1", conversation_id=created.id, event_type="intent_detected", channel=Channel.PHONE,
                              summary="Wohnungssuche erkannt", created_at=NOW)
    repository.add_event(event)

    assert repository.get_conversation(created.id) == created
    assert repository.find_participants(normalized_phone="+4940123") == [participant]
    assert repository.list_messages(created.id) == [message]
    assert repository.list_events(created.id) == [event]
    assert repository.get_state(created.id).state == {}


def test_repository_uses_bound_values_for_search(tmp_path):
    repository = ConversationRepository(tmp_path / "conversation.sqlite3")
    repository.create_conversation(conversation())
    malicious = "x' OR 1=1 --"
    participant = Participant(id="part_1", conversation_id="conv_1", email=malicious, created_at=NOW, updated_at=NOW)
    repository.add_participant(participant, normalized_email=malicious)
    assert repository.find_participants(normalized_email=malicious) == [participant]
    assert repository.find_participants(normalized_email="missing") == []
