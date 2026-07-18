from backend.agents.base_agent import BaseAgent, extract
class RealEstateAgent(BaseAgent):
    name,display_name,description="immobilien","Immobilien-Agent","Immobilientexte und Objektdaten sicher strukturieren"
    capabilities=("expose_text","titel_erstellen","kurzbeschreibung","lagebeschreibung","zielgruppen_text","kapitalanlage_text","verkaufer_argumentation","objektvorteile","social_media_objekttext","anzeigentext","text_ueberarbeiten","objektdaten_zusammenfassen","besichtigungsleitfaden")
    keywords=("immobilientext","objektbeschreibung","lagebeschreibung","exposétext","haus","wohnung","grundstück","wohnfläche")
    def detect_action(self,m):
        n=m.casefold()
        for k,a in (("lagebeschreibung","lagebeschreibung"),("titel","titel_erstellen"),("kurzbeschreibung","kurzbeschreibung"),("kapitalanlage","kapitalanlage_text"),("zielgruppe","zielgruppen_text"),("verkäufer","verkaufer_argumentation"),("vorteil","objektvorteile"),("social media","social_media_objekttext"),("anzeige","anzeigentext"),("überarbeit","text_ueberarbeiten"),("zusammenfass","objektdaten_zusammenfassen"),("besichtigungsleitfaden","besichtigungsleitfaden")):
            if k in n:return a
        return "expose_text"
    def validate(self,r): return [] if any(x in r.message.casefold() for x in ("haus","wohnung","grundstück","immobilie","objekt")) else ["Objektart oder Objektdaten"]
    def simulate(self,r,action):
        m=r.message; fields={"objektart":next((x for x in ("Haus","Wohnung","Grundstück","Doppelhaushälfte") if x.casefold() in m.casefold()),None),"ort":extract(r"(?:für|in)\s+([A-ZÄÖÜ][\wÄÖÜäöüß-]+)",m),"wohnflaeche":extract(r"([\d,.]+)\s*m²",m),"grundstueck":extract(r"grundstück(?:sfläche)?\s*(?:von)?\s*([\d,.]+)",m),"zimmer":extract(r"([\d,.]+)\s*zimmer",m),"baujahr":extract(r"baujahr\s*(\d{4})",m),"zustand":None,"ausstattung":[],"besonderheiten":[x for x in ("Pool","Balkon","Garten") if x.casefold() in m.casefold()],"zielgruppe":"Kapitalanleger" if "kapital" in m.casefold() else None,"ton":"seriös","kanal":None}
        return {"provided_facts":fields,"assumptions":[],"draft":m,"generator_endpoint":"/immobilien-text","external_action_executed":False}
