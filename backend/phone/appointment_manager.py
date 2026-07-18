import json
import sqlite3
from datetime import datetime
from uuid import uuid4

from backend.phone.conversation_memory import ConversationMemory


class AppointmentManager:
    """Local appointment store with a provider-neutral result shape."""

    def __init__(self, memory: ConversationMemory): self.memory = memory

    def book(self, session_id: str, starts_at: datetime, duration_minutes: int = 30, details: dict | None = None) -> dict:
        if duration_minutes < 15 or duration_minutes > 240: raise ValueError("Termindauer muss zwischen 15 und 240 Minuten liegen.")
        appointment_id = f"apt_{uuid4().hex}"
        with self.memory._connect() as db:
            db.execute("INSERT INTO appointments VALUES (?,?,?,?,?,?,?)", (appointment_id, session_id, starts_at.isoformat(), duration_minutes, "reserved_local", json.dumps(details or {}, ensure_ascii=False), self.memory.now()))
        return {"appointment_id": appointment_id, "starts_at": starts_at.isoformat(), "duration_minutes": duration_minutes, "status": "reserved_local", "provider": "local"}
