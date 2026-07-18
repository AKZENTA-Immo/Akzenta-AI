from backend.agents.base_agent import BaseAgent
class DocumentAgent(BaseAgent):
    name,display_name,description="dokumente","Dokumenten-Agent","Vorhandene Dokumentensuche und Wissensbasis nutzen"
    capabilities=("dokument_suchen","dokumente_auflisten","dokument_zusammenfassen","dokument_frage_beantworten","energieausweis_suchen","grundriss_suchen","expose_suchen","kaufvertrag_suchen","teilungserklaerung_suchen","wirtschaftsplan_suchen","protokoll_suchen","grundbuchauszug_suchen")
    keywords=("dokument","pdf","energieausweis","grundriss","kaufvertrag","teilungserklärung","wirtschaftsplan","grundbuchauszug","wissensbasis")
    mutating=False
    def detect_action(self,m):
        n=m.casefold()
        for k,a in (("energieausweis","energieausweis_suchen"),("grundriss","grundriss_suchen"),("kaufvertrag","kaufvertrag_suchen"),("teilungserklärung","teilungserklaerung_suchen"),("wirtschaftsplan","wirtschaftsplan_suchen"),("grundbuch","grundbuchauszug_suchen"),("protokoll","protokoll_suchen"),("exposé","expose_suchen"),("zusammenfass","dokument_zusammenfassen"),("auflisten","dokumente_auflisten"),("was steht","dokument_frage_beantworten")):
            if k in n:return a
        return "dokument_suchen"
    def simulate(self,r,action): return {"query":r.message,"sources":[],"results":[],"empty_result":True,"document_chat_endpoint":"/chat/dokumente","knowledge_search_endpoint":"/wissensbasis/suche","external_action_executed":False}
