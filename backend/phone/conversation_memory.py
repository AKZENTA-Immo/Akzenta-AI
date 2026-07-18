from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend import config


MEMORY_FIELDS = ("name", "phone", "property", "interest", "budget", "appointment", "notes")


class PhonePersistenceError(RuntimeError):
    pass


class ConversationMemory:
    def __init__(self, database_path: str | Path | None = None):
        self.database_path = Path(database_path or config.PHONE_DB_PATH)
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize()
        except (OSError, sqlite3.Error) as exc:
            raise PhonePersistenceError("Telefon-Speicher konnte nicht initialisiert werden.") from exc

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS phone_sessions (
                    session_id TEXT PRIMARY KEY, status TEXT NOT NULL, state_json TEXT NOT NULL,
                    workflow_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS calls (
                    call_id TEXT PRIMARY KEY, session_id TEXT NOT NULL UNIQUE, direction TEXT NOT NULL,
                    caller_phone TEXT, started_at TEXT NOT NULL, ended_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES phone_sessions(session_id)
                );
                CREATE TABLE IF NOT EXISTS call_messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
                    role TEXT NOT NULL, content TEXT NOT NULL, intent TEXT, created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES phone_sessions(session_id)
                );
                CREATE TABLE IF NOT EXISTS call_summary (
                    session_id TEXT PRIMARY KEY, summary_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES phone_sessions(session_id)
                );
                CREATE TABLE IF NOT EXISTS appointments (
                    appointment_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, starts_at TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL, status TEXT NOT NULL, details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL, FOREIGN KEY(session_id) REFERENCES phone_sessions(session_id)
                );
            """)

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create(self, session_id: str, call_id: str, phone: str | None, workflow_id: str | None) -> dict[str, Any]:
        now = self.now(); state = {field: None for field in MEMORY_FIELDS}; state["phone"] = phone; state["notes"] = []
        with self._connect() as db:
            db.execute("INSERT INTO phone_sessions VALUES (?,?,?,?,?,?)", (session_id, "active", json.dumps(state, ensure_ascii=False), workflow_id, now, now))
            db.execute("INSERT INTO calls VALUES (?,?,?,?,?,?)", (call_id, session_id, "inbound", phone, now, None))
        return state

    def get(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            session = db.execute("SELECT * FROM phone_sessions WHERE session_id=?", (session_id,)).fetchone()
            if not session: return None
            messages = [dict(row) for row in db.execute("SELECT role,content,intent,created_at FROM call_messages WHERE session_id=? ORDER BY message_id", (session_id,))]
            summary = db.execute("SELECT summary_json FROM call_summary WHERE session_id=?", (session_id,)).fetchone()
        return {"session_id": session["session_id"], "status": session["status"], "state": json.loads(session["state_json"]),
                "workflow_id": session["workflow_id"], "created_at": session["created_at"], "updated_at": session["updated_at"],
                "messages": messages, "summary": json.loads(summary[0]) if summary else None}

    def update(self, session_id: str, state: dict[str, Any]) -> None:
        with self._connect() as db:
            result = db.execute("UPDATE phone_sessions SET state_json=?,updated_at=? WHERE session_id=? AND status='active'", (json.dumps(state, ensure_ascii=False), self.now(), session_id))
            if result.rowcount != 1: raise KeyError(session_id)

    def add_message(self, session_id: str, role: str, content: str, intent: str | None = None) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO call_messages(session_id,role,content,intent,created_at) VALUES(?,?,?,?,?)", (session_id, role, content, intent, self.now()))

    def finish(self, session_id: str, summary: dict[str, Any]) -> None:
        now = self.now()
        with self._connect() as db:
            result = db.execute("UPDATE phone_sessions SET status='completed',updated_at=? WHERE session_id=? AND status='active'", (now, session_id))
            if result.rowcount != 1: raise KeyError(session_id)
            db.execute("UPDATE calls SET ended_at=? WHERE session_id=?", (now, session_id))
            db.execute("INSERT OR REPLACE INTO call_summary VALUES (?,?,?)", (session_id, json.dumps(summary, ensure_ascii=False), now))

    def statistics(self) -> dict[str, int]:
        with self._connect() as db:
            total = db.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
            active = db.execute("SELECT COUNT(*) FROM phone_sessions WHERE status='active'").fetchone()[0]
            completed = db.execute("SELECT COUNT(*) FROM phone_sessions WHERE status='completed'").fetchone()[0]
            escalated = db.execute("SELECT COUNT(*) FROM phone_sessions WHERE json_extract(state_json, '$.escalation') IS NOT NULL").fetchone()[0]
        return {"calls": total, "active_sessions": active, "completed_sessions": completed, "escalated_sessions": escalated}
