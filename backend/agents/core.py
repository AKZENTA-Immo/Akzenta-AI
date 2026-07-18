import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from backend import config
from backend.models.agent_models import AgentContext, AgentRole

logger = logging.getLogger("akzenta.agents")


class AgentPermissionError(PermissionError): pass


class PromptLoader:
    base_path = config.PROJECT_PATH / "backend" / "prompts"

    @classmethod
    def load(cls, agent: str, version: str = "v1") -> str:
        path = (cls.base_path / agent / f"{version}.md").resolve()
        if cls.base_path.resolve() not in path.parents:
            raise ValueError("Ungültiger Promptpfad.")
        return path.read_text(encoding="utf-8")


class AuditLogger:
    _lock = Lock()

    def record(self, *, agent: str, action: str, context: AgentContext, request_id: str, result: str) -> None:
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "agent": agent, "action": action, "actor_id": context.actor_id, "role": context.role.value, "request_id": request_id, "result": result}
        logger.info("agent_action", extra={"agent_audit": entry})
        try:
            config.AGENT_AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
            with self._lock, config.AGENT_AUDIT_LOG.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            logger.exception("Auditdatei konnte nicht geschrieben werden")


def require_role(context: AgentContext, allowed: set[AgentRole]) -> None:
    if context.role not in allowed:
        raise AgentPermissionError(f"Rolle '{context.role.value}' ist für diese Aktion nicht berechtigt.")


def safe_facts(values: list[str]) -> list[str]:
    return [value.strip()[:500] for value in values if value.strip()][:20]
