from backend.agents.base_agent import BaseAgent
class GeneralAgent(BaseAgent):
    name,display_name,description="allgemein","Allgemeiner Assistent","Sicherer Fallback für allgemeine Aufgaben"
    capabilities=("allgemeine_antwort","text_ueberarbeiten","zusammenfassen","erklaeren","ideen_entwickeln","rueckfrage","aufgabe_unbekannt")
    keywords=()
    mutating=False
    def can_handle(self,message,context=None): return .4
    def detect_action(self,m):
        n=m.casefold()
        if "überarbeit" in n:return "text_ueberarbeiten"
        if "zusammenfass" in n:return "zusammenfassen"
        if "erklär" in n:return "erklaeren"
        if "idee" in n:return "ideen_entwickeln"
        return "rueckfrage" if len(m.split()) < 5 else "allgemeine_antwort"
    def validate(self,r): return ["Konkretes Ziel oder zusätzlicher Kontext"] if self.detect_action(r.message)=="rueckfrage" else []
    def simulate(self,r,action): return {"summary":r.message if action!="rueckfrage" else None,"follow_up_question":"Was genau möchten Sie erreichen?" if action=="rueckfrage" else None,"external_action_executed":False}
