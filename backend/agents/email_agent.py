from backend.agents.base_agent import AgentRequest, BaseAgent, extract
class EmailAgent(BaseAgent):
    name, display_name, description="email","E-Mail-Agent","E-Mail-Entwürfe ohne Versand"
    capabilities=("email_entwurf","email_antwort","terminbestaetigung","unterlagen_anfordern","nachfassmail","verkaufer_ansprache","kapitalanlage_ansprache","absage","dokumentenversand_vorbereiten","besichtigungsbestaetigung","bewertungsanfrage")
    keywords=("e-mail","email","mail","betreff","empfänger","nachfassmail","anschreiben","schreibe herr","schreibe frau")
    def detect_action(self,m):
        n=m.casefold()
        for keys,action in [(("terminbestätigung","termin bestätigen"),"terminbestaetigung"),(("besichtigung","bestätigung"),"besichtigungsbestaetigung"),(("unterlagen","energieausweis","grundriss"),"unterlagen_anfordern"),(("nachfass",),"nachfassmail"),(("antwort",),"email_antwort"),(("absage",),"absage"),(("bewertung",),"bewertungsanfrage"),(("kapitalanlage",),"kapitalanlage_ansprache"),(("verkäufer",),"verkaufer_ansprache")]:
            if any(k in n for k in keys): return action
        return "email_entwurf"
    def validate(self,r): return [] if extract(r"(?:herrn|frau|an|empfänger)\s+([\wÄÖÜäöüß .-]+?)(?:\s+(?:eine|ein|zur|mit)|$)",r.message) else ["Empfänger"]
    def simulate(self,r,action):
        recipient=extract(r"(?:herrn|frau|an|empfänger)\s+([\wÄÖÜäöüß .-]+?)(?:\s+(?:eine|ein|zur|mit)|$)",r.message)
        return {"recipient":recipient,"subject":"AKZENTA Immobilien – Ihre Anfrage","body":r.message,"tone":"freundlich und professionell","purpose":action,"attachments":r.context.get("attachments",[]),"missing_information":[] if recipient else ["Empfänger"],"suggested_next_step":"Entwurf prüfen und später separat freigeben","sent":False,"external_action_executed":False}
