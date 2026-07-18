import re
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, field_validator

from backend.integrations.onoffice.adapter import onoffice_adapter

AgentTarget = Literal["crm", "email", "kalender", "whatsapp", "telefon", "marketing", "dokumente", "immobilien_text", "allgemein"]
ExecutionStatus = Literal["simulated", "blocked", "error"]

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
    uncertain: bool = False
    result: dict[str, str | bool]

class AgentExecutionResponse(BaseModel):
    agent: AgentTarget
    intent: str
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    simulation: bool = True
    approval_required: bool = True
    status: ExecutionStatus
    result: dict[str, Any]
    missing_information: list[str] = Field(default_factory=list)
    proposed_actions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    uncertain: bool = False

@dataclass(frozen=True)
class RoutingDecision:
    agent: AgentTarget
    confidence: float
    reason: str
    uncertain: bool = False

class MessageClassifier(Protocol):
    def classify(self, message: str) -> RoutingDecision: ...

class SimulatedAgent(Protocol):
    agent_name: AgentTarget
    def execute(self, message: str, decision: RoutingDecision) -> AgentExecutionResponse: ...

class DeterministicMessageClassifier:
    """Priorisierte lokale Regeln; später durch einen LLM-Klassifikator ersetzbar."""
    rules: tuple[tuple[int, AgentTarget, tuple[str, ...], str], ...] = (
        (100, "whatsapp", ("whatsapp", "wa-nachricht", "chatnachricht"), "WhatsApp-Schlüsselwörter erkannt"),
        (95, "telefon", ("anrufen", "telefon", "telefonat", "rückruf", "gesprächsleitfaden"), "Telefon-Schlüsselwörter erkannt"),
        (90, "email", ("e-mail", "email", "mail", "anschreiben", "schreibe herr", "schreibe frau"), "E-Mail-Schlüsselwörter erkannt"),
        (85, "kalender", ("termin", "kalender", "besichtigung vereinbaren", "meeting", "verfügbarkeit", "uhrzeit"), "Termin- oder Kalender-Schlüsselwörter erkannt"),
        (80, "crm", ("crm", "onoffice", "kontakt", "kundendaten", "lead", "notiz hinterlegen", "verkäufer erfassen"), "CRM-Schlüsselwörter erkannt"),
        (75, "marketing", ("marketing", "social media", "instagram", "linkedin", "kampagne", "werbeanzeige", "posting", "cta"), "Marketing-Schlüsselwörter erkannt"),
        (70, "immobilien_text", ("immobilientext", "exposé", "expose", "objektbeschreibung", "anzeigentext", "wohnung beschreiben", "haus beschreiben"), "Immobilientext-Schlüsselwörter erkannt"),
        (60, "dokumente", ("dokument", "unterlage", "datei", "pdf", "wissensbasis", "suche nach", "finde"), "Dokumenten-Schlüsselwörter erkannt"),
    )

    def classify(self, message: str) -> RoutingDecision:
        normalized = re.sub(r"\s+", " ", message.casefold())
        matches: list[tuple[int, int, AgentTarget, str]] = []
        for priority, agent, keywords, reason in self.rules:
            hits = sum(keyword in normalized for keyword in keywords)
            if hits:
                matches.append((hits, priority, agent, reason))
        if not matches:
            return RoutingDecision("allgemein", 0.5, "Keine eindeutigen Agenten-Schlüsselwörter erkannt", True)
        matches.sort(key=lambda item: (item[1], item[0]), reverse=True)
        hits, _, agent, reason = matches[0]
        ambiguous = len(matches) > 1
        confidence = min(0.99, 0.9 + (hits - 1) * 0.04) if not ambiguous else 0.68
        if ambiguous:
            reason += "; mehrere Anliegen erkannt, Prioritätsregel angewendet"
        return RoutingDecision(agent, confidence, reason, ambiguous)

def _extract(pattern: str, message: str) -> str | None:
    match = re.search(pattern, message, re.IGNORECASE)
    return match.group(1).strip() if match else None

class BaseSimulationAgent:
    agent_name: AgentTarget = "allgemein"
    intent = "allgemeine_unterstützung"
    warning = "Simulation: Es wurde keine externe Aktion ausgeführt."

    def build(self, message: str) -> tuple[dict[str, Any], list[str], list[str]]:
        return {"summary": message[:500]}, [], ["Antwortvorschlag prüfen"]

    def execute(self, message: str, decision: RoutingDecision) -> AgentExecutionResponse:
        result, missing, actions = self.build(message)
        result["external_action_executed"] = False
        return AgentExecutionResponse(agent=self.agent_name, intent=self.intent, confidence=decision.confidence,
            reasoning=decision.reason, status="simulated", result=result, missing_information=missing,
            proposed_actions=actions, warnings=[self.warning, "Freigabe erforderlich vor jeder vorgesehenen externen Aktion."], uncertain=decision.uncertain)

class CrmSimulationAgent(BaseSimulationAgent):
    agent_name, intent = "crm", "crm_änderungsvorschlag"
    def build(self, message):
        lead = _extract(r"(?:kontakt|lead)\s+(?:für\s+)?([\wÄÖÜäöüß .-]+)", message)
        source = "onOffice" if onoffice_adapter.active else "Simulation"
        return {
            "contact_or_lead": lead,
            "data_source": source,
            "read_only": True,
            "facts_from_onoffice": [],
            "input_information": {"message": message, "contact_or_lead": lead},
            "proposed_changes": [message],
            "change_proposal": message,
            "crm_changed": False,
        }, ([] if lead else ["Kontakt- oder Lead-Referenz"]), ["CRM-Änderung als Vorschau prüfen", "Menschliche Freigabe einholen"]

class EmailSimulationAgent(BaseSimulationAgent):
    agent_name, intent = "email", "email_entwurf"
    def build(self, message):
        recipient = _extract(r"(?:herrn|frau|an)\s+([\wÄÖÜäöüß .-]+?)(?:\s+eine|\s+ein|\s+mit|$)", message)
        subject = "AKZENTA Immobilien – Ihre Anfrage"
        return {"recipient": recipient, "subject": subject, "body": message, "sent": False}, ([] if recipient else ["Empfänger", "E-Mail-Adresse"]), ["Entwurf fachlich prüfen", "Versandfreigabe einholen"]

class CalendarSimulationAgent(BaseSimulationAgent):
    agent_name, intent = "kalender", "terminvorschlag"
    def build(self, message):
        duration = _extract(r"(\d{1,3})\s*(?:minuten|min\.)", message)
        period = _extract(r"((?:am|morgen|heute|nächste\w*)[^,.]*)", message)
        return {"appointment_type": "Besichtigung" if "besichtigung" in message.casefold() else "Termin", "duration_minutes": int(duration) if duration else 30, "preferred_period": period, "participants": [], "calendar_entry_created": False}, (["Gewünschter Zeitraum"] if not period else []) + ["Teilnehmer"], ["Verfügbarkeit prüfen", "Terminvorschlag freigeben"]

class WhatsAppSimulationAgent(BaseSimulationAgent):
    agent_name, intent = "whatsapp", "whatsapp_entwurf"
    def build(self, message):
        return {"reply_draft": message, "sent": False}, ["Empfänger oder Chatreferenz"], ["Antwortentwurf prüfen", "Versandfreigabe einholen"]

class PhoneSimulationAgent(BaseSimulationAgent):
    agent_name, intent = "telefon", "telefongespräch_vorbereitung"
    def build(self, message):
        return {"call_goal": message, "talk_track": ["Begrüßung", "Anliegen klären", "Nächste Schritte vereinbaren"], "call_started": False}, ["Gesprächspartner", "Rufnummer", "Relevante Kundendaten"], ["Gesprächsleitfaden prüfen", "Anruf separat freigeben"]

class MarketingSimulationAgent(BaseSimulationAgent):
    agent_name, intent = "marketing", "marketing_entwurf"
    def build(self, message):
        channel = next((item for item in ("Instagram", "LinkedIn", "Social Media") if item.casefold() in message.casefold()), None)
        return {"target_group": None, "channel": channel, "format": "Post", "hook": "Immobilienkompetenz aus Hamburg", "content": message, "cta": "Jetzt beraten lassen", "published": False}, (["Zielgruppe"] + ([] if channel else ["Kanal"])), ["Inhalt und CI prüfen", "Veröffentlichungsfreigabe einholen"]

class DocumentSimulationAgent(BaseSimulationAgent):
    agent_name, intent = "dokumente", "dokumentenanfrage"
    def build(self, message): return {"query": message, "document_chat_available": True}, [], ["Bestehenden Dokumentenchat verwenden"]

class RealEstateTextSimulationAgent(BaseSimulationAgent):
    agent_name, intent = "immobilien_text", "immobilientext_entwurf"
    def build(self, message): return {"brief": message, "text_generator_available": True}, ["Objektdaten", "Zielgruppe"], ["Bestehenden Immobilientextgenerator verwenden", "Entwurf prüfen"]

class GeneralSimulationAgent(BaseSimulationAgent): pass

class CentralAgentManager:
    def __init__(self, classifier: MessageClassifier | None = None, agents: dict[AgentTarget, SimulatedAgent] | None = None):
        self.classifier = classifier or DeterministicMessageClassifier()
        self.agents = agents or {agent.agent_name: agent for agent in (CrmSimulationAgent(), EmailSimulationAgent(), CalendarSimulationAgent(), WhatsAppSimulationAgent(), PhoneSimulationAgent(), MarketingSimulationAgent(), DocumentSimulationAgent(), RealEstateTextSimulationAgent(), GeneralSimulationAgent())}

    def route(self, request: AgentManagerRequest) -> AgentManagerResult:
        decision = self.classifier.classify(request.message)
        return AgentManagerResult(agent=decision.agent, confidence=decision.confidence, reason=decision.reason, original_message=request.message,
            simulation=request.simulation, uncertain=decision.uncertain, result={"status": "simulated" if request.simulation else "blocked", "external_action_executed": False})

    def execute(self, request: AgentManagerRequest) -> AgentExecutionResponse:
        decision = self.classifier.classify(request.message)
        if not request.simulation:
            return AgentExecutionResponse(agent=decision.agent, intent="execution_blocked", confidence=decision.confidence,
                reasoning=decision.reason, simulation=False, status="blocked", result={"external_action_executed": False},
                proposed_actions=["Simulationsmodus aktivieren"], warnings=["Echte Ausführung ist in Version 1.5 gesperrt."], uncertain=decision.uncertain)
        try:
            return self.agents[decision.agent].execute(request.message, decision)
        except Exception:
            return AgentExecutionResponse(agent=decision.agent, intent="agent_error", confidence=decision.confidence,
                reasoning=decision.reason, status="error", result={"external_action_executed": False},
                warnings=["Der simulierte Agent konnte die Anfrage nicht sicher verarbeiten."], uncertain=decision.uncertain)

central_agent_manager = CentralAgentManager()
