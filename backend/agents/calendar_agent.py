from backend.agents.base_agent import BaseAgent, extract
class CalendarAgent(BaseAgent):
    name,display_name,description="kalender","Kalender-Agent","Termine sicher vorbereiten"
    capabilities=("termin_vorschlagen","termin_vorbereiten","termin_verschieben_vorbereiten","termin_absagen_vorbereiten","verfuegbarkeit_pruefen","erinnerung_vorbereiten","strategiegespraech_planen","besichtigung_planen","video_call_planen","rueckruf_planen")
    keywords=("termin","kalender","besichtigung"," uhr","montag","freitag","video-call","verschieben")
    def detect_action(self,m):
        n=m.casefold()
        for k,a in (("verschieb","termin_verschieben_vorbereiten"),("absag","termin_absagen_vorbereiten"),("verfügbarkeit","verfuegbarkeit_pruefen"),("erinner","erinnerung_vorbereiten"),("strategie","strategiegespraech_planen"),("besichtigung","besichtigung_planen"),("video","video_call_planen"),("rückruf","rueckruf_planen"),("vorschlag","termin_vorschlagen")):
            if k in n:return a
        return "termin_vorbereiten"
    def validate(self,r):
        n=r.message.casefold(); missing=[]
        if not any(x in n for x in ("heute","morgen","montag","dienstag","mittwoch","donnerstag","freitag","samstag","sonntag","nächste woche")) and not extract(r"\d{1,2}\.\d{1,2}(?:\.\d{2,4})?",r.message): missing.append("Datum")
        if not extract(r"\b(\d{1,2}(?::\d{2})?)\s*uhr\b",r.message): missing.append("Uhrzeit")
        return missing
    def simulate(self,r,action):
        m=r.message; return {"datum":extract(r"((?:heute|morgen|montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag|nächste woche)|\d{1,2}\.\d{1,2}(?:\.\d{2,4})?)",m),"uhrzeit":extract(r"\b(\d{1,2}(?::\d{2})?)\s*uhr\b",m),"dauer_minuten":int(extract(r"(\d{1,3})\s*(?:minuten|min)",m) or 30),"titel":action.replace("_"," "),"teilnehmer":r.context.get("participants",[]),"ort":extract(r"(?:in|bei)\s+([^,.]+)",m),"terminart":action,"beschreibung":m,"erinnerung":"vorbereiten" if "erinner" in m.casefold() else None,"calendar_entry_created":False,"external_action_executed":False}
