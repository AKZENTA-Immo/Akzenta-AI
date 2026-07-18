import re
from backend.agents.base_agent import AgentRequest, BaseAgent, extract

class CrmAgent(BaseAgent):
    name, display_name, description = "crm", "CRM-Agent", "Leads und Kundendaten sicher vorbereiten"
    capabilities = ("lead_suchen", "lead_anlegen_vorbereiten", "lead_aktualisieren_vorbereiten", "notiz_vorbereiten", "wiedervorlage_vorbereiten", "lead_qualifizieren", "verkaufer_lead_erfassen", "kapitalanlage_lead_erfassen", "kundendaten_zusammenfassen", "onoffice_kontakt_suchen", "knowledge_lookup")
    keywords = ("crm", "lead", "kunde", "interessent", "eigentümer", "verkäufer", "wiedervorlage", "onoffice")
    def detect_action(self, m):
        n=m.casefold()
        if "onoffice" in n or ("kontakt" in n and "such" in n): return "onoffice_kontakt_suchen"
        if "such" in n: return "lead_suchen"
        if "wiedervorlage" in n: return "wiedervorlage_vorbereiten"
        if "notiz" in n or "ergänze" in n: return "notiz_vorbereiten"
        if "kapitalanlage" in n: return "kapitalanlage_lead_erfassen"
        if "verkäufer" in n or "eigentümer" in n: return "verkaufer_lead_erfassen"
        if "qualifiz" in n: return "lead_qualifizieren"
        if any(x in n for x in ("anlegen", "erfassen", "neuen")): return "lead_anlegen_vorbereiten"
        if "zusammenfass" in n: return "kundendaten_zusammenfassen"
        return "lead_aktualisieren_vorbereiten"
    def validate(self, r): return [] if extract(r"(?:lead|kunde|interessent|eigentümer|verkäufer|kontakt)\s+([\wÄÖÜäöüß .-]+)", r.message) else ["Name oder Kontaktreferenz"]
    def simulate(self, r, action):
        m=r.message; budget=extract(r"([\d.]+(?:,\d+)?)\s*(?:euro|€)",m)
        name=extract(r"(?:lead|kunde|interessent|eigentümer|verkäufer|kontakt)\s+([\wÄÖÜäöüß .-]+)",m)
        return {"lead":{"name":name,"email":extract(r"([\w.+-]+@[\w.-]+\.[A-Za-z]{2,})",m),"telefon":extract(r"(\+?[\d][\d /-]{6,})",m),"lead_typ":"kapitalanlage" if "kapital" in m.casefold() else "verkauf" if any(x in m.casefold() for x in ("verkäufer","eigentümer")) else None,"budget":budget,"objektart":next((x for x in ("Haus","Wohnung","Grundstück") if x.casefold() in m.casefold()),None),"ort":extract(r"(?:in|aus)\s+([A-ZÄÖÜ][\wÄÖÜäöüß-]+)",m),"zeitraum":extract(r"(?:bis|am|für)\s+([^,.]+)",m),"notiz":m if action=="notiz_vorbereiten" else None,"prioritaet":"hoch" if "dringend" in m.casefold() else None,"kaufmotiv":"Kapitalanlage" if "kapital" in m.casefold() else None,"verkaufsabsicht":"verkaufen" in m.casefold()},"data_source":"Simulation","read_only":True,"facts_from_onoffice":[],"proposed_action":action,"crm_changed":False,"external_action_executed":False}
