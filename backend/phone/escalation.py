from dataclasses import dataclass


@dataclass(frozen=True)
class EscalationDecision:
    required: bool
    reason: str | None = None


class EscalationManager:
    _REASONS = {
        "Mitarbeiter angefordert": ("mitarbeiter", "person sprechen", "menschen sprechen"),
        "Beschwerde oder Konflikt": ("beschwerde", "unzufrieden", "streit", "betrug"),
        "Rechtliche Frage": ("rechtlich", "anwalt", "vertrag", "haftung", "gesetz"),
        "Technisches Problem": ("technisches problem", "funktioniert nicht", "verbindung abgebrochen"),
        "Unsicherheit": ("weiß ich nicht", "unsicher", "verstehe ich nicht"),
    }

    def evaluate(self, text: str) -> EscalationDecision:
        normalized = text.casefold()
        for reason, terms in self._REASONS.items():
            if any(term in normalized for term in terms): return EscalationDecision(True, reason)
        return EscalationDecision(False)
