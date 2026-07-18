"""Repository-Schicht für Conversation-Persistenz; SQL bleibt hier gekapselt."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from backend import config
from backend.conversation.migrations import migrate
from backend.conversation.models import (
    Attachment,
    Channel,
    Conversation,
    ConversationEvent,
    ConversationMemory,
    ConversationState,
    ConversationStatus,
    Message,
    MessageDirection,
    MessageLink,
    Participant,
)


class ConversationPersistenceError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


class ConversationRepository:
    """SQLite-Repository mit einer Verbindung pro Operation und gebundenen Parametern."""

    def __init__(self, database_path: str | Path | None = None, timeout: float = 10.0):
        self.database_path = Path(database_path or config.CONVERSATION_DB_PATH)
        self.timeout = timeout
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            with self._transaction(immediate=True) as connection:
                migrate(connection)
        except (OSError, sqlite3.Error) as exc:
            raise ConversationPersistenceError("Conversation-Speicher konnte nicht initialisiert werden.") from exc

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=self.timeout, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def _transaction(self, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _conversation(row: sqlite3.Row) -> Conversation:
        return Conversation(
            id=row["id"], subject=row["subject"], status=row["status"], primary_channel=row["primary_channel"],
            created_at=row["created_at"], updated_at=row["updated_at"], archived_at=row["archived_at"],
            metadata=json.loads(row["metadata_json"]),
        )

    def create_conversation(self, conversation: Conversation) -> Conversation:
        with self._transaction(immediate=True) as connection:
            connection.execute(
                "INSERT INTO conversations(id,subject,status,primary_channel,created_at,updated_at,archived_at,metadata_json) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (conversation.id, conversation.subject, conversation.status.value,
                 conversation.primary_channel.value if conversation.primary_channel else None,
                 conversation.created_at.isoformat(), conversation.updated_at.isoformat(),
                 conversation.archived_at.isoformat() if conversation.archived_at else None, _json(conversation.metadata)),
            )
            connection.execute(
                "INSERT INTO conversation_state(conversation_id,state_json,updated_at) VALUES (?,?,?)",
                (conversation.id, "{}", conversation.created_at.isoformat()),
            )
        return self.get_conversation(conversation.id)  # type: ignore[return-value]

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        return self._conversation(row) if row else None

    def list_conversations(self, *, status: ConversationStatus | None = None, limit: int = 50, offset: int = 0) -> list[Conversation]:
        sql = "SELECT * FROM conversations"
        params: list[Any] = []
        if status:
            sql += " WHERE status = ?"
            params.append(status.value)
        sql += " ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?"
        params.extend((limit, offset))
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._conversation(row) for row in rows]

    def set_status(self, conversation_id: str, status: ConversationStatus) -> Conversation | None:
        now = utc_now().isoformat()
        with self._transaction(immediate=True) as connection:
            connection.execute(
                "UPDATE conversations SET status=?, updated_at=?, archived_at=? WHERE id=?",
                (status.value, now, now if status == ConversationStatus.ARCHIVED else None, conversation_id),
            )
        return self.get_conversation(conversation_id)

    @staticmethod
    def _participant(row: sqlite3.Row) -> Participant:
        return Participant(**{key: row[key] for key in ("id", "conversation_id", "kind", "display_name", "phone", "mobile", "email", "crm_id", "onoffice_id", "created_at", "updated_at")}, metadata=json.loads(row["metadata_json"]))

    def add_participant(self, participant: Participant, *, normalized_phone: str | None = None,
                        normalized_mobile: str | None = None, normalized_email: str | None = None) -> Participant:
        with self._transaction(immediate=True) as connection:
            connection.execute(
                "INSERT INTO participants(id,conversation_id,kind,display_name,phone,mobile,email,crm_id,onoffice_id,normalized_phone,normalized_mobile,normalized_email,created_at,updated_at,metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (participant.id, participant.conversation_id, participant.kind, participant.display_name, participant.phone,
                 participant.mobile, participant.email, participant.crm_id, participant.onoffice_id, normalized_phone,
                 normalized_mobile, normalized_email, participant.created_at.isoformat(), participant.updated_at.isoformat(),
                 _json(participant.metadata)),
            )
        return participant

    def list_participants(self, conversation_id: str) -> list[Participant]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM participants WHERE conversation_id=? ORDER BY created_at,id", (conversation_id,)).fetchall()
        return [self._participant(row) for row in rows]

    def find_participants(self, *, normalized_phone: str | None = None, normalized_mobile: str | None = None,
                          normalized_email: str | None = None, crm_id: str | None = None,
                          onoffice_id: str | None = None) -> list[Participant]:
        candidates = [("normalized_phone", normalized_phone), ("normalized_mobile", normalized_mobile),
                      ("normalized_email", normalized_email), ("crm_id", crm_id), ("onoffice_id", onoffice_id)]
        active = [(column, value) for column, value in candidates if value]
        if not active:
            return []
        where = " OR ".join(f"{column} = ?" for column, _ in active)
        with self._connect() as connection:
            rows = connection.execute(f"SELECT * FROM participants WHERE {where} ORDER BY created_at,id", [value for _, value in active]).fetchall()
        return [self._participant(row) for row in rows]

    @staticmethod
    def _message(row: sqlite3.Row) -> Message:
        return Message(id=row["id"], conversation_id=row["conversation_id"], participant_id=row["participant_id"],
                       channel=row["channel"], direction=row["direction"], message_type=row["message_type"],
                       content=row["content"], external_id=row["external_id"], created_at=row["created_at"],
                       updated_at=row["updated_at"], metadata=json.loads(row["metadata_json"]))

    def add_message(self, message: Message) -> Message:
        with self._transaction(immediate=True) as connection:
            connection.execute(
                "INSERT INTO messages(id,conversation_id,participant_id,channel,direction,message_type,content,external_id,created_at,updated_at,metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (message.id, message.conversation_id, message.participant_id, message.channel.value, message.direction.value,
                 message.message_type, message.content, message.external_id, message.created_at.isoformat(),
                 message.updated_at.isoformat(), _json(message.metadata)),
            )
            connection.execute("UPDATE conversations SET updated_at=? WHERE id=?", (message.created_at.isoformat(), message.conversation_id))
        return message

    def list_messages(self, conversation_id: str, limit: int = 500) -> list[Message]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at,id LIMIT ?", (conversation_id, limit)).fetchall()
        return [self._message(row) for row in rows]

    def add_event(self, event: ConversationEvent) -> ConversationEvent:
        with self._transaction(immediate=True) as connection:
            connection.execute(
                "INSERT INTO events(id,conversation_id,event_type,channel,actor_id,summary,created_at,metadata_json) VALUES (?,?,?,?,?,?,?,?)",
                (event.id, event.conversation_id, event.event_type, event.channel.value, event.actor_id, event.summary,
                 event.created_at.isoformat(), _json(event.metadata)),
            )
            connection.execute("UPDATE conversations SET updated_at=? WHERE id=?", (event.created_at.isoformat(), event.conversation_id))
        return event

    def list_events(self, conversation_id: str, limit: int = 500) -> list[ConversationEvent]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM events WHERE conversation_id=? ORDER BY created_at,id LIMIT ?", (conversation_id, limit)).fetchall()
        return [ConversationEvent(id=row["id"], conversation_id=row["conversation_id"], event_type=row["event_type"],
                                  channel=row["channel"], actor_id=row["actor_id"], summary=row["summary"],
                                  created_at=row["created_at"], metadata=json.loads(row["metadata_json"])) for row in rows]

    def add_attachment(self, attachment: Attachment) -> Attachment:
        with self._transaction(immediate=True) as connection:
            connection.execute(
                "INSERT INTO attachments(id,filename,content_type,size_bytes,content_hash,storage_reference,document_id,created_at,metadata_json) VALUES (?,?,?,?,?,?,?,?,?)",
                (attachment.id, attachment.filename, attachment.content_type, attachment.size_bytes, attachment.content_hash,
                 attachment.storage_reference, attachment.document_id, attachment.created_at.isoformat(), _json(attachment.metadata)),
            )
        return attachment

    def find_attachment(self, *, content_hash: str | None = None, document_id: str | None = None) -> Attachment | None:
        if not content_hash and not document_id:
            return None
        clauses, params = [], []
        if content_hash:
            clauses.append("content_hash=?"); params.append(content_hash)
        if document_id:
            clauses.append("document_id=?"); params.append(document_id)
        with self._connect() as connection:
            row = connection.execute(f"SELECT * FROM attachments WHERE {' OR '.join(clauses)} LIMIT 1", params).fetchone()
        return Attachment(id=row["id"], filename=row["filename"], content_type=row["content_type"], size_bytes=row["size_bytes"],
                          content_hash=row["content_hash"], storage_reference=row["storage_reference"], document_id=row["document_id"],
                          created_at=row["created_at"], metadata=json.loads(row["metadata_json"])) if row else None

    def add_tag(self, conversation_id: str, name: str, created_at: datetime | None = None) -> None:
        with self._transaction(immediate=True) as connection:
            connection.execute("INSERT OR IGNORE INTO tags(conversation_id,name,created_at) VALUES (?,?,?)", (conversation_id, name, (created_at or utc_now()).isoformat()))

    def list_tags(self, conversation_id: str) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute("SELECT name FROM tags WHERE conversation_id=? ORDER BY name", (conversation_id,)).fetchall()
        return [row["name"] for row in rows]

    def add_message_link(self, link: MessageLink) -> MessageLink:
        with self._transaction(immediate=True) as connection:
            connection.execute("INSERT INTO message_links(id,source_message_id,target_type,target_id,relation_type,created_at,metadata_json) VALUES (?,?,?,?,?,?,?)",
                               (link.id, link.source_message_id, link.target_type, link.target_id, link.relation_type, link.created_at.isoformat(), _json(link.metadata)))
        return link

    def get_state(self, conversation_id: str) -> ConversationState | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM conversation_state WHERE conversation_id=?", (conversation_id,)).fetchone()
        return ConversationState(conversation_id=row["conversation_id"], current_intent=row["current_intent"], assigned_agent=row["assigned_agent"],
                                 workflow_id=row["workflow_id"], crm_lead_id=row["crm_lead_id"], state=json.loads(row["state_json"]),
                                 updated_at=row["updated_at"]) if row else None

    def save_state(self, state: ConversationState) -> ConversationState:
        with self._transaction(immediate=True) as connection:
            connection.execute("UPDATE conversation_state SET current_intent=?,assigned_agent=?,workflow_id=?,crm_lead_id=?,state_json=?,updated_at=? WHERE conversation_id=?",
                               (state.current_intent, state.assigned_agent, state.workflow_id, state.crm_lead_id, _json(state.state), state.updated_at.isoformat(), state.conversation_id))
        return self.get_state(state.conversation_id)  # type: ignore[return-value]

    def add_memory(self, memory: ConversationMemory) -> ConversationMemory:
        with self._transaction(immediate=True) as connection:
            connection.execute("INSERT INTO conversation_memory(id,conversation_id,memory_type,content,importance,source_message_id,created_at,expires_at,metadata_json) VALUES (?,?,?,?,?,?,?,?,?)",
                               (memory.id, memory.conversation_id, memory.memory_type, memory.content, memory.importance, memory.source_message_id,
                                memory.created_at.isoformat(), memory.expires_at.isoformat() if memory.expires_at else None, _json(memory.metadata)))
        return memory

    def list_memory(self, conversation_id: str, limit: int = 100) -> list[ConversationMemory]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM conversation_memory WHERE conversation_id=? AND (expires_at IS NULL OR expires_at>?) ORDER BY importance DESC,created_at DESC LIMIT ?",
                                      (conversation_id, utc_now().isoformat(), limit)).fetchall()
        return [ConversationMemory(id=row["id"], conversation_id=row["conversation_id"], memory_type=row["memory_type"], content=row["content"],
                                   importance=row["importance"], source_message_id=row["source_message_id"], created_at=row["created_at"],
                                   expires_at=row["expires_at"], metadata=json.loads(row["metadata_json"])) for row in rows]
