from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from backend import config
from backend.phone.escalation import EscalationManager
from backend.phone.intent_classifier import IntentClassifier, PhoneIntent
from backend.rag.knowledge_service import NOT_FOUND, KnowledgeService


SECURE_INFORMATION_MISSING = "Darauf habe ich aktuell keine gesicherte Information."
KNOWLEDGE_INTENTS = {PhoneIntent.DOCUMENTS, PhoneIntent.PRICE, PhoneIntent.PROPERTY_QUESTION, PhoneIntent.FINANCING, PhoneIntent.INVESTMENT}


class DialogManager:
    def __init__(self, knowledge_service: KnowledgeService, classifier: IntentClassifier | None = None,
                 escalation: EscalationManager | None = None):
        self.knowledge_service = knowledge_service
        self.classifier = classifier or IntentClassifier()
        self.escalation = escalation or EscalationManager()

    @staticmethod
    def update_state(state: dict[str, Any], text: str, intent: PhoneIntent, appointment_start: datetime | None = None) -> dict[str, Any]:
        updated = dict(state); notes = list(updated.get("notes") or [])
        name = re.search(r"(?:ich (?:bin|heiße)|mein name ist)\s+([A-ZÄÖÜ][\wÄÖÜäöüß-]+(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß-]+)?)", text, re.IGNORECASE)
        phone = re.search(r"(?:telefon|nummer|erreichen unter)\D*((?:\+|00)?\d[\d /-]{5,}\d)", text, re.IGNORECASE)
        budget = re.search(r"(?:budget|bis zu|maximal)\D{0,15}([\d.]+(?:,\d+)?)\s*(€|euro|tausend|mio)?", text, re.IGNORECASE)
        prop = re.search(r"(?:objekt|wohnung|haus|immobilie)\s+(?:in|am|an der|mit der adresse)?\s*([^,.!?]{3,80})", text, re.IGNORECASE)
        if name: updated["name"] = name.group(1).strip()
        if phone: updated["phone"] = phone.group(1).strip()
        if budget: updated["budget"] = " ".join(part for part in budget.groups() if part).strip()
        if prop: updated["property"] = prop.group(1).strip()
        if intent not in {PhoneIntent.GREETING, PhoneIntent.GOODBYE, PhoneIntent.UNKNOWN}: updated["interest"] = intent.value
        if appointment_start: updated["appointment"] = appointment_start.isoformat()
        notes.append(text.strip()); updated["notes"] = notes[-20:]
        return updated

    def respond(self, state: dict[str, Any], text: str, appointment_start: datetime | None = None) -> tuple[str, PhoneIntent, dict[str, Any]]:
        intent = self.classifier.classify(text)
        state = self.update_state(state, text, intent, appointment_start)
        decision = self.escalation.evaluate(text)
        if decision.required:
            state["escalation"] = decision.reason
            return "Ich übergebe Ihr Anliegen an einen Mitarbeiter.", intent, state
        if intent in KNOWLEDGE_INTENTS:
            result = self.knowledge_service.ask(text, config.PHONE_KNOWLEDGE_TOP_K)
            answer = result.get("answer", NOT_FOUND)
            return (SECURE_INFORMATION_MISSING if answer == NOT_FOUND else answer), intent, state
        responses = {
            PhoneIntent.GREETING: "Guten Tag, hier ist AKZENTA Immobilien. Wie kann ich Ihnen helfen?",
            PhoneIntent.CALLBACK: "Gern bereite ich einen Rückruf vor. Unter welcher Nummer erreichen wir Sie?",
            PhoneIntent.SELLER: "Gern nehme ich Ihr Verkaufsanliegen auf. Um welches Objekt handelt es sich?",
            PhoneIntent.VIEWING: "Gern bereite ich eine Besichtigung vor. Welches Objekt interessiert Sie?",
            PhoneIntent.APPOINTMENT: "Ich habe Ihren Terminwunsch aufgenommen." if appointment_start else "Welcher Termin passt Ihnen?",
            PhoneIntent.REJECTION: "Verstanden. Ich vermerke, dass aktuell kein Interesse besteht.",
            PhoneIntent.GOODBYE: "Vielen Dank für Ihren Anruf. Auf Wiederhören.",
            PhoneIntent.UNKNOWN: "Könnten Sie Ihr Anliegen bitte etwas genauer beschreiben?",
        }
        return responses.get(intent, "Wie kann ich Sie dabei unterstützen?"), intent, state
