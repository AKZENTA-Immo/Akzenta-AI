import re
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, Field, field_validator

AgentTarget = Literal["crm", "email", "kalender", "dokumente", "immobilien_text", "allgemein"]

class AgentManagerRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    simulation: bool = True

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Die Nachricht darf nicht leer sein.")
        return value

class AgentManagerResult(BaseModel):
    agent: AgentTarget
    confidence: float = Field(ge=0, le=1)
    reason: str
    original_message: str
    simulation: bool
    result: dict[str, str | bool]

@dataclass(frozen=True)
class RoutingDecision:
    agent: AgentTarget
    confidence: float
    reason: str

class MessageClassifier(Protocol):
    def classify(self, message: str) -> RoutingDecision: ...

class DeterministicMessageClassifier:
    """Lokaler Regelklassifikator; später durch einen LLM-Klassifikator ersetzbar."""
    rules: tuple[tuple[AgentTarget, tuple[str, ...], str], ...] = (
        ("email", ("e-mail", "email", "mail", "anschreiben", "nachricht senden", "schreibe herr", "schreibe frau"), "E-Mail-Schlüsselwörter erkannt"),
        ("kalender", ("termin", "kalender", "besichtigung vereinbaren", "meeting", "verfügbarkeit", "uhrzeit"), "Termin- oder Kalender-Schlüsselwörter erkannt"),
        ("crm", ("crm", "onoffice", "kontakt", "kundendaten", "lead", "notiz hinterlegen", "verkäufer erfassen"), "CRM-Schlüsselwörter erkannt"),
        ("dokumente", ("dokument", "unterlage", "datei", "pdf", "wissensbasis", "suche nach", "finde"), "Dokumenten-Schlüsselwörter erkannt"),
        ("immobilien_text", ("immobilientext", "exposé", "expose", "objektbeschreibung", "anzeigentext", "wohnung beschreiben", "haus beschreiben"), "Immobilientext-Schlüsselwörter erkannt"),
    )

    def classify(self, message: str) -> RoutingDecision:
        normalized = re.sub(r"\s+", " ", message.casefold())
        matches: list[tuple[int, int, AgentTarget, str]] = []
        for priority, (agent, keywords, reason) in enumerate(self.rules):
            hits = sum(keyword in normalized for keyword in keywords)
            if hits:
                matches.append((hits, -priority, agent, reason))
        if not matches:
            return RoutingDecision("allgemein", 0.5, "Keine eindeutigen Agenten-Schlüsselwörter erkannt")
        hits, _, agent, reason = max(matches)
        return RoutingDecision(agent, min(0.99, 0.9 + (hits - 1) * 0.04), reason)

class CentralAgentManager:
    def __init__(self, classifier: MessageClassifier | None = None):
        self.classifier = classifier or DeterministicMessageClassifier()

    def route(self, request: AgentManagerRequest) -> AgentManagerResult:
        decision = self.classifier.classify(request.message)
        return AgentManagerResult(agent=decision.agent, confidence=decision.confidence, reason=decision.reason,
            original_message=request.message, simulation=request.simulation,
            result={"status": "simulated" if request.simulation else "blocked", "external_action_executed": False})

central_agent_manager = CentralAgentManager()
