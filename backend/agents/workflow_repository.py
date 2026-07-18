"""SQLite persistence for safe workflows, approvals, and immutable audit events."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from backend import config
from backend.models.agent_models import ApprovalRecord, ApprovalStatus, AuditEvent, WorkflowCoreResponse, WorkflowRecord


class PersistenceError(RuntimeError):
    pass


class UnsupportedSchemaVersion(PersistenceError):
    pass


class ConcurrentUpdateError(PersistenceError):
    pass


SCHEMA_VERSION = 2


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


class WorkflowRepository:
    """Thread-safe-by-connection SQLite repository; one connection per operation."""

    def __init__(self, database_path: str | Path | None = None, timeout: float = 10.0):
        configured = database_path or os.getenv("AKZENTA_WORKFLOW_DB")
        self.database_path = Path(configured) if configured else config.PROJECT_PATH / "data" / "workflow_engine.sqlite3"
        self.timeout = timeout
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            self.initialize_schema()
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("Workflow-Speicher konnte nicht initialisiert werden.") from exc

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

    def initialize_schema(self) -> None:
        with self._transaction(immediate=True) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            row = connection.execute("SELECT MAX(version) AS version FROM schema_version").fetchone()
            current = row["version"] if row and row["version"] is not None else 0
            if current > SCHEMA_VERSION:
                raise UnsupportedSchemaVersion("Die Workflow-Datenbank verwendet eine neuere, nicht unterstützte Schema-Version.")
            if current < 1:
                connection.executescript("""
                    CREATE TABLE IF NOT EXISTS workflows (
                        workflow_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                        status TEXT NOT NULL, workflow_fingerprint TEXT NOT NULL,
                        request_payload TEXT NOT NULL, response_payload TEXT NOT NULL,
                        approval_required INTEGER NOT NULL CHECK (approval_required IN (0,1)),
                        external_actions_performed INTEGER NOT NULL CHECK (external_actions_performed IN (0,1)),
                        execution_mode TEXT NOT NULL, executed_at TEXT
                    );
                    CREATE TABLE IF NOT EXISTS approvals (
                        approval_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL REFERENCES workflows(workflow_id),
                        status TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                        requested_by TEXT, decided_at TEXT, decided_by TEXT, reason TEXT, executed_at TEXT,
                        workflow_fingerprint TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_workflows_created ON workflows(created_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_approvals_workflow ON approvals(workflow_id, created_at DESC);
                    CREATE TABLE IF NOT EXISTS audit_events (
                        event_id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
                        workflow_id TEXT, approval_id TEXT, event_type TEXT NOT NULL,
                        previous_status TEXT, new_status TEXT, actor TEXT, message TEXT,
                        metadata TEXT NOT NULL, created_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_audit_workflow ON audit_events(workflow_id, created_at, event_id);
                """)
                connection.execute("INSERT INTO schema_version(version, applied_at) VALUES (?, ?)", (1, utc_now().isoformat()))
            if current < 2:
                connection.executescript("""
                    CREATE TABLE IF NOT EXISTS workflow_definitions (
                        definition_id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
                        version TEXT NOT NULL, enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
                        definition_payload TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS workflow_instances (
                        workflow_id TEXT PRIMARY KEY REFERENCES workflows(workflow_id), definition_id TEXT NOT NULL REFERENCES workflow_definitions(definition_id),
                        name TEXT NOT NULL, status TEXT NOT NULL, current_step_id TEXT, created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL, completed_at TEXT, requested_by TEXT, input_payload TEXT NOT NULL,
                        output_payload TEXT NOT NULL, approval_id TEXT, execution_mode TEXT NOT NULL CHECK(execution_mode='simulation'),
                        external_actions_performed INTEGER NOT NULL CHECK(external_actions_performed=0), metadata_payload TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS workflow_steps (
                        workflow_id TEXT NOT NULL REFERENCES workflow_instances(workflow_id), step_id TEXT NOT NULL,
                        position INTEGER NOT NULL, name TEXT NOT NULL, agent TEXT NOT NULL, action TEXT NOT NULL,
                        status TEXT NOT NULL, attempt INTEGER NOT NULL, max_retries INTEGER NOT NULL,
                        depends_on TEXT NOT NULL, condition_payload TEXT NOT NULL, input_payload TEXT NOT NULL,
                        output_payload TEXT NOT NULL, error TEXT, started_at TEXT, completed_at TEXT, updated_at TEXT NOT NULL,
                        PRIMARY KEY(workflow_id, step_id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_instances_created ON workflow_instances(created_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_steps_workflow ON workflow_steps(workflow_id, position);
                """)
                connection.execute("INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES (?, ?)", (2, utc_now().isoformat()))

    @staticmethod
    def _audit(connection: sqlite3.Connection, *, entity_type: str, entity_id: str, event_type: str,
               workflow_id: str | None = None, approval_id: str | None = None,
               previous_status: str | None = None, new_status: str | None = None,
               actor: str | None = None, message: str | None = None,
               metadata: dict[str, Any] | None = None, created_at: datetime | None = None) -> None:
        connection.execute(
            "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"evt_{uuid4().hex}", entity_type, entity_id, workflow_id, approval_id, event_type,
             previous_status, new_status, actor, message, canonical_json(metadata or {}),
             (created_at or utc_now()).isoformat()),
        )

    def save_workflow(self, request_payload: dict[str, Any], workflow: WorkflowCoreResponse) -> WorkflowRecord:
        now = workflow.created_at
        response_payload = workflow.model_dump(mode="json")
        try:
            with self._transaction(immediate=True) as connection:
                connection.execute(
                    "INSERT INTO workflows VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (workflow.workflow_id, now.isoformat(), now.isoformat(), workflow.status,
                     workflow.workflow_fingerprint, canonical_json(request_payload), canonical_json(response_payload),
                     int(workflow.approval_required), 0, "simulation", None),
                )
                self._audit(connection, entity_type="workflow", entity_id=workflow.workflow_id,
                            workflow_id=workflow.workflow_id, event_type="workflow_created",
                            new_status=workflow.status, actor=request_payload.get("context", {}).get("actor_id"),
                            message="Workflow sicher vorbereitet und persistent gespeichert.", created_at=now)
        except sqlite3.Error as exc:
            raise PersistenceError("Workflow konnte nicht sicher gespeichert werden.") from exc
        return self.get_workflow(workflow.workflow_id)  # type: ignore[return-value]

    @staticmethod
    def _workflow(row: sqlite3.Row) -> WorkflowRecord:
        return WorkflowRecord(
            workflow_id=row["workflow_id"], created_at=row["created_at"], updated_at=row["updated_at"],
            status=row["status"], workflow_fingerprint=row["workflow_fingerprint"],
            request_payload=json.loads(row["request_payload"]), response_payload=json.loads(row["response_payload"]),
            approval_required=bool(row["approval_required"]), external_actions_performed=bool(row["external_actions_performed"]),
            execution_mode=row["execution_mode"], executed_at=row["executed_at"],
        )

    def get_workflow(self, workflow_id: str) -> WorkflowRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM workflows WHERE workflow_id = ?", (workflow_id,)).fetchone()
        return self._workflow(row) if row else None

    def workflow_exists(self, workflow_id: str) -> bool:
        return self.get_workflow(workflow_id) is not None

    def list_workflows(self, limit: int = 50, status: str | None = None) -> list[WorkflowRecord]:
        sql, params = "SELECT * FROM workflows", []
        if status:
            sql, params = sql + " WHERE status = ?", [status]
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._workflow(row) for row in rows]

    def update_workflow_status(self, workflow_id: str, status: str, executed_at: datetime | None = None) -> None:
        with self._transaction(immediate=True) as connection:
            connection.execute("UPDATE workflows SET status=?, updated_at=?, executed_at=? WHERE workflow_id=?",
                               (status, utc_now().isoformat(), executed_at.isoformat() if executed_at else None, workflow_id))

    def verify_workflow_fingerprint(self, workflow_id: str, calculated: str) -> bool:
        workflow = self.get_workflow(workflow_id)
        return bool(workflow and workflow.workflow_fingerprint == calculated)

    @staticmethod
    def _approval(row: sqlite3.Row) -> ApprovalRecord:
        return ApprovalRecord(**dict(row))

    def save_approval(self, approval: ApprovalRecord) -> ApprovalRecord:
        try:
            with self._transaction(immediate=True) as connection:
                connection.execute("INSERT INTO approvals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                    approval.approval_id, approval.workflow_id, approval.status.value, approval.created_at.isoformat(),
                    approval.expires_at.isoformat(), approval.requested_by,
                    approval.decided_at.isoformat() if approval.decided_at else None, approval.decided_by,
                    approval.reason, approval.executed_at.isoformat() if approval.executed_at else None,
                    approval.workflow_fingerprint))
                self._audit(connection, entity_type="approval", entity_id=approval.approval_id,
                            workflow_id=approval.workflow_id, approval_id=approval.approval_id,
                            event_type="approval_created", new_status="pending", actor=approval.requested_by,
                            message="Freigabe angefordert.", created_at=approval.created_at)
        except sqlite3.IntegrityError as exc:
            raise PersistenceError("Freigabe konnte nicht sicher gespeichert werden.") from exc
        return approval

    def get_approval(self, approval_id: str) -> ApprovalRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)).fetchone()
        return self._approval(row) if row else None

    def get_pending_approval_for_workflow(self, workflow_id: str) -> ApprovalRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM approvals WHERE workflow_id=? AND status='pending' ORDER BY created_at DESC LIMIT 1",
                (workflow_id,)).fetchone()
        return self._approval(row) if row else None

    def list_approvals(self, limit: int = 50, workflow_id: str | None = None, status: str | None = None) -> list[ApprovalRecord]:
        clauses, params = [], []
        if workflow_id:
            clauses.append("workflow_id = ?"); params.append(workflow_id)
        if status:
            clauses.append("status = ?"); params.append(status)
        sql = "SELECT * FROM approvals" + ((" WHERE " + " AND ".join(clauses)) if clauses else "") + " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._approval(row) for row in rows]

    def expire_approval(self, approval_id: str, now: datetime) -> ApprovalRecord | None:
        with self._transaction(immediate=True) as connection:
            row = connection.execute("SELECT * FROM approvals WHERE approval_id=?", (approval_id,)).fetchone()
            if not row:
                return None
            if row["status"] in ("pending", "approved") and now >= datetime.fromisoformat(row["expires_at"]):
                connection.execute("UPDATE approvals SET status='expired' WHERE approval_id=? AND status IN ('pending','approved')", (approval_id,))
                self._audit(connection, entity_type="approval", entity_id=approval_id, workflow_id=row["workflow_id"],
                            approval_id=approval_id, event_type="approval_expired", previous_status=row["status"],
                            new_status="expired", message="Freigabe ist abgelaufen.", created_at=now)
            updated = connection.execute("SELECT * FROM approvals WHERE approval_id=?", (approval_id,)).fetchone()
        return self._approval(updated)

    def update_approval_decision(self, approval_id: str, decision: ApprovalStatus, decided_at: datetime,
                                 decided_by: str | None, reason: str | None) -> ApprovalRecord:
        with self._transaction(immediate=True) as connection:
            result = connection.execute(
                "UPDATE approvals SET status=?, decided_at=?, decided_by=?, reason=? WHERE approval_id=? AND status='pending'",
                (decision.value, decided_at.isoformat(), decided_by, reason, approval_id))
            if result.rowcount != 1:
                raise ConcurrentUpdateError("Freigabestatus wurde zwischenzeitlich geändert.")
            row = connection.execute("SELECT * FROM approvals WHERE approval_id=?", (approval_id,)).fetchone()
            self._audit(connection, entity_type="approval", entity_id=approval_id, workflow_id=row["workflow_id"],
                        approval_id=approval_id, event_type=f"approval_{decision.value}", previous_status="pending",
                        new_status=decision.value, actor=decided_by, message="Freigabeentscheidung gespeichert.", created_at=decided_at)
        return self._approval(row)

    def mark_approval_executed(self, approval_id: str, expected_fingerprint: str, calculated_fingerprint: str,
                               executed_at: datetime) -> ApprovalRecord:
        with self._transaction(immediate=True) as connection:
            row = connection.execute("SELECT * FROM approvals WHERE approval_id=?", (approval_id,)).fetchone()
            if not row or row["status"] != "approved":
                raise ConcurrentUpdateError("Freigabe ist nicht mehr ausführbar.")
            workflow = connection.execute("SELECT * FROM workflows WHERE workflow_id=?", (row["workflow_id"],)).fetchone()
            if (not workflow or row["workflow_fingerprint"] != expected_fingerprint
                    or workflow["workflow_fingerprint"] != calculated_fingerprint
                    or row["workflow_fingerprint"] != calculated_fingerprint):
                self._audit(connection, entity_type="workflow", entity_id=row["workflow_id"], workflow_id=row["workflow_id"],
                            approval_id=approval_id, event_type="integrity_check_failed", previous_status="approved",
                            new_status="approved", message="Workflow-Integritätsprüfung fehlgeschlagen.", created_at=executed_at)
                return self._approval(row)
            self._audit(connection, entity_type="approval", entity_id=approval_id, workflow_id=row["workflow_id"],
                        approval_id=approval_id, event_type="execution_started", previous_status="approved",
                        new_status="approved", message="Lokale Simulation gestartet.", created_at=executed_at)
            result = connection.execute("UPDATE approvals SET status='executed', executed_at=? WHERE approval_id=? AND status='approved'",
                                        (executed_at.isoformat(), approval_id))
            if result.rowcount != 1:
                raise ConcurrentUpdateError("Freigabe wurde bereits ausgeführt.")
            connection.execute("UPDATE workflows SET status='executed', updated_at=?, executed_at=? WHERE workflow_id=?",
                               (executed_at.isoformat(), executed_at.isoformat(), row["workflow_id"]))
            self._audit(connection, entity_type="approval", entity_id=approval_id, workflow_id=row["workflow_id"],
                        approval_id=approval_id, event_type="execution_completed", previous_status="approved",
                        new_status="executed", message="Workflow ausschließlich lokal simuliert.", created_at=executed_at)
            updated = connection.execute("SELECT * FROM approvals WHERE approval_id=?", (approval_id,)).fetchone()
        return self._approval(updated)

    def add_audit_event(self, **event: Any) -> None:
        with self._transaction(immediate=True) as connection:
            self._audit(connection, **event)

    def save_workflow_definition(self, definition: Any) -> None:
        payload = definition.model_dump(mode="json") if hasattr(definition, "model_dump") else definition
        now = utc_now().isoformat()
        with self._transaction(immediate=True) as connection:
            connection.execute("""INSERT INTO workflow_definitions VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(definition_id) DO UPDATE SET name=excluded.name,description=excluded.description,
                version=excluded.version,enabled=excluded.enabled,definition_payload=excluded.definition_payload,updated_at=excluded.updated_at""",
                (payload["definition_id"], payload["name"], payload.get("description", ""), payload.get("version", "1.0"),
                 int(payload.get("enabled", True)), canonical_json(payload), now, now))

    def get_workflow_definition(self, definition_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT definition_payload FROM workflow_definitions WHERE definition_id=?", (definition_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def list_workflow_definitions(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT definition_payload FROM workflow_definitions ORDER BY definition_id").fetchall()
        return [json.loads(row[0]) for row in rows]

    def create_workflow_instance(self, instance: dict[str, Any], steps: list[dict[str, Any]], fingerprint: str) -> None:
        now = instance["created_at"]
        public = {"workflow_id": instance["workflow_id"], "status": instance["status"], "steps": []}
        with self._transaction(immediate=True) as connection:
            connection.execute("INSERT INTO workflows VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (instance["workflow_id"], now, now, instance["status"], fingerprint, canonical_json(instance["input"]),
                 canonical_json(public), 1, 0, "simulation", None))
            connection.execute("INSERT INTO workflow_instances VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (instance["workflow_id"], instance["definition_id"], instance["name"], instance["status"], None, now, now,
                 None, instance.get("requested_by"), canonical_json(instance["input"]), "{}", None, "simulation", 0,
                 canonical_json(instance.get("metadata", {}))))
            for step in steps:
                connection.execute("INSERT INTO workflow_steps VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (instance["workflow_id"], step["step_id"], step["position"], step["name"], step["agent"], step["action"],
                     "pending", 0, step["max_retries"], canonical_json(step["depends_on"]), canonical_json(step["condition"]),
                     "{}", "{}", None, None, None, now))
            self._audit(connection, entity_type="workflow", entity_id=instance["workflow_id"], workflow_id=instance["workflow_id"],
                        event_type="workflow_instance_created", new_status="created")

    @staticmethod
    def _instance(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        for key in ("input_payload", "output_payload", "metadata_payload"):
            value[key.removesuffix("_payload")] = json.loads(value.pop(key))
        value["external_actions_performed"] = bool(value["external_actions_performed"])
        return value

    def get_workflow_instance(self, workflow_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM workflow_instances WHERE workflow_id=?", (workflow_id,)).fetchone()
        return self._instance(row) if row else None

    def list_workflow_instances(self, limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM workflow_instances"; params: list[Any] = []
        if status: sql += " WHERE status=?"; params.append(status)
        sql += " ORDER BY created_at DESC LIMIT ?"; params.append(limit)
        with self._connect() as connection: rows = connection.execute(sql, params).fetchall()
        return [self._instance(row) for row in rows]

    @staticmethod
    def _engine_step(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        for key in ("depends_on", "condition_payload", "input_payload", "output_payload"):
            target = {"condition_payload":"condition", "input_payload":"input", "output_payload":"output"}.get(key, key)
            value[target] = json.loads(value.pop(key))
        return value

    def get_workflow_steps(self, workflow_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection: rows = connection.execute("SELECT * FROM workflow_steps WHERE workflow_id=? ORDER BY position", (workflow_id,)).fetchall()
        return [self._engine_step(row) for row in rows]

    def get_workflow_step(self, workflow_id: str, step_id: str) -> dict[str, Any] | None:
        with self._connect() as connection: row = connection.execute("SELECT * FROM workflow_steps WHERE workflow_id=? AND step_id=?", (workflow_id, step_id)).fetchone()
        return self._engine_step(row) if row else None

    def update_engine_workflow(self, workflow_id: str, status: str, current_step_id: str | None = None, approval_id: str | None = None, completed: bool = False) -> None:
        now = utc_now().isoformat()
        with self._transaction(immediate=True) as connection:
            result = connection.execute("UPDATE workflow_instances SET status=?,current_step_id=?,approval_id=COALESCE(?,approval_id),updated_at=?,completed_at=CASE WHEN ? THEN ? ELSE completed_at END WHERE workflow_id=?",
                (status, current_step_id, approval_id, now, int(completed), now, workflow_id))
            if result.rowcount != 1: raise ConcurrentUpdateError("Workflowstatus konnte nicht aktualisiert werden.")
            connection.execute("UPDATE workflows SET status=?,updated_at=? WHERE workflow_id=?", (status, now, workflow_id))

    def update_step_status(self, workflow_id: str, step_id: str, status: str, *, error: str | None = None, output: dict[str, Any] | None = None, expected: tuple[str, ...] | None = None, increment_attempt: bool = False) -> None:
        now = utc_now().isoformat(); expected = expected or ("pending", "running", "waiting", "failed", "blocked")
        placeholders = ",".join("?" for _ in expected)
        sql = f"""UPDATE workflow_steps SET status=?,error=?,output_payload=COALESCE(?,output_payload),updated_at=?,
            started_at=CASE WHEN ?='running' THEN ? ELSE started_at END,
            completed_at=CASE WHEN ? IN ('completed','failed','skipped') THEN ? ELSE completed_at END,
            attempt=attempt+? WHERE workflow_id=? AND step_id=? AND status IN ({placeholders})"""
        with self._transaction(immediate=True) as connection:
            result = connection.execute(sql, (status, error, canonical_json(output) if output is not None else None, now, status, now, status, now,
                int(increment_attempt), workflow_id, step_id, *expected))
            if result.rowcount != 1: raise ConcurrentUpdateError("Schritt wurde bereits oder in einem anderen Zustand verarbeitet.")

    def increment_step_attempt(self, workflow_id: str, step_id: str) -> None:
        with self._transaction(immediate=True) as connection:
            connection.execute("UPDATE workflow_steps SET attempt=attempt+1,updated_at=? WHERE workflow_id=? AND step_id=?", (utc_now().isoformat(), workflow_id, step_id))

    def set_workflow_approval(self, workflow_id: str, approval_id: str) -> None:
        self.update_engine_workflow(workflow_id, "waiting_for_approval", approval_id=approval_id)

    def mark_workflow_completed(self, workflow_id: str) -> None: self.update_engine_workflow(workflow_id, "completed", completed=True)
    def cancel_workflow(self, workflow_id: str) -> None: self.update_engine_workflow(workflow_id, "cancelled")
    def append_audit_event(self, **event: Any) -> None: self.add_audit_event(**event)

    @staticmethod
    def _event(row: sqlite3.Row) -> AuditEvent:
        values = dict(row); values["metadata"] = json.loads(values["metadata"])
        return AuditEvent(**values)

    def list_audit_events(self, limit: int = 100) -> list[AuditEvent]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM audit_events ORDER BY created_at, rowid LIMIT ?", (limit,)).fetchall()
        return [self._event(row) for row in rows]

    def get_workflow_audit(self, workflow_id: str, limit: int = 100) -> list[AuditEvent]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM audit_events WHERE workflow_id=? ORDER BY created_at, rowid LIMIT ?",
                                      (workflow_id, limit)).fetchall()
        return [self._event(row) for row in rows]
