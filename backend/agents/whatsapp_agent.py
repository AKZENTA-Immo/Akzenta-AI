from backend.agents.base_agent import BaseAgent, extract
class WhatsAppAgent(BaseAgent):
    name,display_name,description="whatsapp","WhatsApp-Agent","Kurznachrichten ausschließlich als Entwurf"
    capabilities=("antwort_entwurf","terminbestaetigung","nachfassnachricht","unterlagen_anfordern","objektinformation","lead_qualifizierung","rueckrufbitte","absage","besichtigungserinnerung","kontaktaufnahme")
    keywords=("whatsapp","chatnachricht","kurze nachricht","wa-nachricht")
    def detect_action(self,m):
        n=m.casefold()
        for k,a in (("terminbestätigung","terminbestaetigung"),("nachfass","nachfassnachricht"),("unterlagen","unterlagen_anfordern"),("objektinformation","objektinformation"),("qualifiz","lead_qualifizierung"),("rückruf","rueckrufbitte"),("absage","absage"),("erinner","besichtigungserinnerung"),("kontakt","kontaktaufnahme")):
            if k in n:return a
        return "antwort_entwurf"
    def validate(self,r): return [] if extract(r"(?:an|für)\s+([\wÄÖÜäöüß .-]+)",r.message) else ["Empfänger oder Chatreferenz"]
    def simulate(self,r,action):
        recipient=extract(r"(?:an|für)\s+([\wÄÖÜäöüß .-]+)",r.message); return {"recipient":recipient,"message":r.message,"tone":"freundlich und kurz","length":len(r.message),"missing_information":[] if recipient else ["Empfänger oder Chatreferenz"],"suggested_next_step":"Entwurf prüfen und separat freigeben","sent":False,"external_action_executed":False}
