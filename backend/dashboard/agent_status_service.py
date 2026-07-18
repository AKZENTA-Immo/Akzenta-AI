from datetime import datetime,timezone
from pathlib import Path
from .models import AgentState,AgentStatusView
class AgentStatusService:
    def __init__(self,phone_db:Path,workflow_db:Path,knowledge_db:Path,dashboard_db:Path): self.paths=(phone_db,workflow_db,knowledge_db,dashboard_db)
    def list(self,agent=None):
        now=datetime.now(timezone.utc); names=('Phone Agent','CRM Agent','Email Agent','Marketing Agent','Workflow Engine','Knowledge Engine','Ollama','SQLite'); result=[]
        for name in names:
            status=AgentState.IDLE; message='Bereit (lokaler Lesestatus)'
            if name=='SQLite' and not any(p.exists() for p in self.paths): status=AgentState.UNAVAILABLE; message='Noch keine lokale Datenbank vorhanden'
            if name=='Ollama': status=AgentState.IDLE; message='Nicht aktiv geprüft'
            item=AgentStatusView(name=name,status=status,checked_at=now,message=message)
            if not agent or agent.casefold() in name.casefold(): result.append(item)
        return result
