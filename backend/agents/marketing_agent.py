from backend.agents.base_agent import BaseAgent
class MarketingAgent(BaseAgent):
    name,display_name,description="marketing","Marketing-Agent","Marketinginhalte ohne Veröffentlichung vorbereiten"
    capabilities=("social_media_post","newsletter","kampagnenidee","video_script","hook","call_to_action","landingpage_text","zielgruppenanalyse","content_plan","nachfasskampagne","verkauferkampagne","kapitalanlagekampagne","retargeting_text","google_ads_text","testimonial_anfrage")
    keywords=("marketing","kampagne","newsletter","instagram","facebook","social media","video","hook","landingpage","google ads")
    def detect_action(self,m):
        n=m.casefold()
        for k,a in (("newsletter","newsletter"),("video","video_script"),("hook","hook"),("call to action","call_to_action"),("landingpage","landingpage_text"),("zielgruppenanalyse","zielgruppenanalyse"),("content plan","content_plan"),("nachfass","nachfasskampagne"),("verkäuferkampagne","verkauferkampagne"),("kapitalanlage","kapitalanlagekampagne"),("retargeting","retargeting_text"),("google ads","google_ads_text"),("testimonial","testimonial_anfrage"),("kampagne","kampagnenidee")):
            if k in n:return a
        return "social_media_post"
    def simulate(self,r,action):
        n=r.message.casefold(); channel=next((x for x in ("Instagram","Facebook","LinkedIn","Google Ads","Newsletter") if x.casefold() in n),"Social Media")
        return {"channel":channel,"target_group":"Kapitalanleger" if "kapital" in n else "Eigentümer" if "eigentümer" in n or "verkäufer" in n else None,"objective":action,"hook":"Immobilienkompetenz, die weiterdenkt","content":r.message,"call_to_action":"Jetzt beraten lassen","variants":[],"compliance_notes":["Fakten und Pflichtangaben vor Veröffentlichung prüfen"],"published":False,"external_action_executed":False}
