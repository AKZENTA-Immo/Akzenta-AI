from backend.agents.base_agent import BaseAgent
class PhoneAgent(BaseAgent):
    name,display_name,description="telefon","Telefon-Agent","Telefonate ausschließlich textuell vorbereiten"
    capabilities=("gespraechsleitfaden","anruf_vorbereiten","eingehenden_anruf_simulieren","lead_qualifizierung","terminvereinbarung","verkaufergespraech","kapitalanlagegespraech","rueckruf_vorbereiten","einwandbehandlung","gespraech_zusammenfassen")
    keywords=("anrufen","telefon","rückruf","gesprächsleitfaden","einwand","telefongespräch")
    def detect_action(self,m):
        n=m.casefold()
        for k,a in (("leitfaden","gespraechsleitfaden"),("eingehend","eingehenden_anruf_simulieren"),("qualifiz","lead_qualifizierung"),("termin","terminvereinbarung"),("verkäufer","verkaufergespraech"),("kapitalanlage","kapitalanlagegespraech"),("rückruf","rueckruf_vorbereiten"),("einwand","einwandbehandlung"),("zusammenfass","gespraech_zusammenfassen")):
            if k in n:return a
        return "anruf_vorbereiten"
    def simulate(self,r,action): return {"greeting":"Guten Tag, hier ist AKZENTA Immobilien.","objective":r.message,"questions":["Wie können wir Sie konkret unterstützen?","Welche Rahmenbedingungen sind wichtig?"],"qualification":[],"objections":[],"responses":[],"next_step":"Leitfaden prüfen und Anruf separat freigeben","call_summary_template":{"anliegen":"","ergebnis":"","naechster_schritt":""},"call_started":False,"external_action_executed":False}
