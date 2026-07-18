from __future__ import annotations
import asyncio,json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from .models import DashboardEvent,DashboardNotification

EVENT_TYPES=frozenset({'conversation_started','conversation_finished','lead_created','lead_scored','appointment_created','followup_created','escalation_created','workflow_started','workflow_completed','workflow_failed','knowledge_lookup','agent_error'})
class EventService:
    def __init__(self,database_path:str|Path): self.database_path=Path(database_path); self.database_path.parent.mkdir(parents=True,exist_ok=True); self.initialize_schema()
    def _connect(self): db=sqlite3.connect(self.database_path); db.row_factory=sqlite3.Row; return db
    def initialize_schema(self):
        with self._connect() as db: db.executescript('''CREATE TABLE IF NOT EXISTS dashboard_events(id TEXT PRIMARY KEY,event_type TEXT NOT NULL,severity TEXT NOT NULL,title TEXT NOT NULL,message TEXT NOT NULL,entity_type TEXT,entity_id TEXT,metadata_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL); CREATE INDEX IF NOT EXISTS idx_dashboard_events_created ON dashboard_events(created_at DESC); CREATE TABLE IF NOT EXISTS dashboard_notifications(id TEXT PRIMARY KEY,title TEXT NOT NULL,message TEXT NOT NULL,severity TEXT NOT NULL,is_read INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL); CREATE INDEX IF NOT EXISTS idx_dashboard_notifications_created ON dashboard_notifications(created_at DESC);''')
    def list_events(self,*,date_from=None,date_to=None,limit=50,offset=0,after=None):
        clauses=[]; params=[]
        if date_from: clauses.append('created_at>=?'); params.append(date_from.isoformat())
        if date_to: clauses.append('created_at<=?'); params.append(date_to.isoformat())
        if after: clauses.append('created_at>?'); params.append(after.isoformat())
        where=' WHERE '+' AND '.join(clauses) if clauses else ''
        with self._connect() as db: rows=db.execute('SELECT * FROM dashboard_events'+where+' ORDER BY created_at DESC LIMIT ? OFFSET ?',(*params,limit,offset)).fetchall()
        return [DashboardEvent(id=r['id'],event_type=r['event_type'],severity=r['severity'],title=r['title'],message=r['message'],entity_type=r['entity_type'],entity_id=r['entity_id'],metadata=json.loads(r['metadata_json']),created_at=r['created_at']) for r in rows]
    def list_notifications(self,limit=50,offset=0):
        with self._connect() as db: rows=db.execute('SELECT * FROM dashboard_notifications ORDER BY created_at DESC LIMIT ? OFFSET ?',(limit,offset)).fetchall()
        return [DashboardNotification(id=r['id'],title=r['title'],message=r['message'],severity=r['severity'],read=bool(r['is_read']),created_at=r['created_at']) for r in rows]
    async def stream(self,poll_interval=.5,keepalive=15.0):
        cursor=datetime.now(timezone.utc); elapsed=0.0
        while True:
            events=list(reversed(self.list_events(after=cursor,limit=100)))
            if events:
                for event in events:
                    cursor=max(cursor,event.created_at); yield f"event: {event.event_type}\ndata: {event.model_dump_json()}\n\n"
                elapsed=0
            elif elapsed>=keepalive: yield ': keepalive\n\n'; elapsed=0
            await asyncio.sleep(poll_interval); elapsed+=poll_interval
