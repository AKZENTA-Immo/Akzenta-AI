import re
from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

AgentStatusValue = Literal["simulated", "completed", "rejected", "validation_error", "confirmation_required", "not_supported", "error"]


class AgentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    simulation: bool = True
    context: dict[str, Any] = Field(default_factory=dict)
    user_id: str | None = Field(default=None, max_length=100)
    conversation_id: str | None = Field(default=None, max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Die Nachricht darf nicht leer sein.")
        return value


class AgentResponse(BaseModel):
    agent: str
    display_name: str
    action: str
    status: AgentStatusValue
    simulation: bool
    confidence: float = Field(ge=0, le=1)
    reason: str
    result: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    requires_confirmation: bool = True
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def sanitize(value: Any) -> Any:
    if isinstance(value, str):
        return re.sub(r"(?:[A-Za-z]:\\|/)(?:[^\s<>:\"|?*]+[\\/])+[^\s<>:\"|?*]*", "[interner Pfad]", value)
    if isinstance(value, dict): return {str(key): sanitize(item) for key, item in value.items()}
    if isinstance(value, list): return [sanitize(item) for item in value]
    return value


def extract(pattern: str, message: str) -> str | None:
    match = re.search(pattern, message, re.IGNORECASE)
    return match.group(1).strip(" .,!") if match else None


class BaseAgent(ABC):
    name = "base"
    display_name = "Basis-Agent"
    description = "Gemeinsame sichere Agentenschnittstelle"
    capabilities: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    mutating = True

    def can_handle(self, message: str, context: dict[str, Any] | None = None) -> float:
        normalized = message.casefold()
        hits = sum(keyword in normalized for keyword in self.keywords)
        return min(.99, .55 + hits * .12) if hits else 0.0

    @abstractmethod
    def detect_action(self, message: str) -> str: ...

    def validate(self, request: AgentRequest) -> list[str]:
        return []

    @abstractmethod
    def simulate(self, request: AgentRequest, action: str) -> dict[str, Any]: ...

    def execute(self, request: AgentRequest, *, confidence: float | None = None, reason: str | None = None) -> AgentResponse:
        action = self.detect_action(request.message)
        missing = self.validate(request)
        if not request.simulation and self.mutating:
            return AgentResponse(agent=self.name, display_name=self.display_name, action=action, status="rejected", simulation=False,
                confidence=confidence or self.can_handle(request.message), reason=reason or "Externe Ausführung ist gesperrt.",
                warnings=["Keine externe oder verändernde Aktion wurde ausgeführt."], missing_information=missing,
                result={"external_action_executed": False}, requires_confirmation=True)
        try:
            result = sanitize(self.simulate(request, action))
            status = "confirmation_required" if self.name == "allgemein" and missing else "simulated"
            return AgentResponse(agent=self.name, display_name=self.display_name, action=action, status=status, simulation=True,
                confidence=confidence or self.can_handle(request.message), reason=reason or "Lokale Regel erkannt.", result=result,
                warnings=["Sichere Simulation: Es wurde keine externe Aktion ausgeführt."], missing_information=missing,
                requires_confirmation=True, metadata={"external_actions_enabled": False})
        except Exception:
            return AgentResponse(agent=self.name, display_name=self.display_name, action=action, status="error", simulation=True,
                confidence=confidence or 0, reason=reason or "Agentenfehler sicher abgefangen.", result={"external_action_executed": False},
                warnings=["Die Anfrage konnte nicht sicher simuliert werden."], error="Interner Agentenfehler.")

    def health_check(self) -> dict[str, Any]:
        return {"name": self.name, "display_name": self.display_name, "available": True, "simulation": True, "capabilities": list(self.capabilities)}

    def knowledge_lookup(self, query: str, top_k: int = 5) -> dict[str, Any]:
        """Expliziter, lokaler Lesezugriff für dafür freigeschaltete Agenten."""
        if "knowledge_lookup" not in self.capabilities:
            raise PermissionError("Agent darf die Wissensbasis nicht verwenden.")
        from backend.rag.knowledge_service import KnowledgeService
        return KnowledgeService().search(query, top_k)
