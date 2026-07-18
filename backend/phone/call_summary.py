from typing import Any


class LeadScore:
    @staticmethod
    def calculate(state: dict[str, Any]) -> int:
        score = 0
        if state.get("budget"): score += 20
        if state.get("appointment"): score += 20
        if state.get("interest"): score += 20
        if state.get("property"): score += 15
        interests = str(state.get("interest") or "").casefold()
        if "verk" in interests: score += 15
        if "kapital" in interests or "anlage" in interests: score += 10
        return min(score, 100)


class CallSummary:
    def create(self, session: dict[str, Any]) -> dict[str, Any]:
        state = session["state"]; messages = session["messages"]
        open_items = [label for key, label in (("name", "Name"), ("property", "Objekt"), ("budget", "Budget")) if not state.get(key)]
        next_steps = []
        if state.get("appointment"): next_steps.append("Termin vorbereiten")
        if state.get("escalation"): next_steps.append("Mitarbeiter übernimmt")
        if not next_steps: next_steps.append("Lead nachfassen")
        return {
            "summary": f"Lokales Telefongespräch mit {len([m for m in messages if m['role'] == 'user'])} Kundenbeiträgen.",
            "interest": state.get("interest"), "lead_score": LeadScore.calculate(state), "open_items": open_items,
            "next_steps": next_steps, "appointment": state.get("appointment"), "notes": state.get("notes") or [],
        }
