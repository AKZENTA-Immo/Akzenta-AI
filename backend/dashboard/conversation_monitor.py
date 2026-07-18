from __future__ import annotations
import json, sqlite3
from datetime import datetime
from pathlib import Path
from .models import ConversationMessageView, ConversationOverview, KnowledgeSourceView

def _json(value, default):
    try: return json.loads(value) if value else default
    except (TypeError, json.JSONDecodeError): return default

class ConversationMonitor:
    def __init__(self, database_path: str|Path): self.database_path=Path(database_path)
    def _connect(self):
        db=sqlite3.connect(self.database_path); db.row_factory=sqlite3.Row; return db
    def list(self, *, date_from=None,date_to=None,status=None,search=None,limit=50,offset=0):
        if not self.database_path.exists(): return []
        clauses=[]; params=[]
        if date_from: clauses.append("s.created_at >= ?"); params.append(date_from.isoformat())
        if date_to: clauses.append("s.created_at <= ?"); params.append(date_to.isoformat())
        if status: clauses.append("s.status = ?"); params.append(status)
        if search:
            clauses.append("(s.session_id LIKE ? OR c.caller_phone LIKE ? OR json_extract(s.state_json,'$.name') LIKE ? OR json_extract(s.state_json,'$.email') LIKE ? OR json_extract(s.state_json,'$.property') LIKE ?)"); params += [f"%{search}%"]*5
        where=" WHERE "+" AND ".join(clauses) if clauses else ""
        sql="SELECT s.*,c.direction,c.caller_phone,c.started_at,c.ended_at,cs.summary_json FROM phone_sessions s LEFT JOIN calls c ON c.session_id=s.session_id LEFT JOIN call_summary cs ON cs.session_id=s.session_id"+where+" ORDER BY s.created_at DESC LIMIT ? OFFSET ?"
        with self._connect() as db: rows=db.execute(sql,(*params,limit,offset)).fetchall()
        return [self._row(row) for row in rows]
    def get(self, session_id):
        items=self.list(search=session_id,limit=100)
        item=next((x for x in items if x.session_id==session_id),None)
        if not item: return None
        with self._connect() as db: rows=db.execute("SELECT role,content,intent,created_at FROM call_messages WHERE session_id=? ORDER BY message_id",(session_id,)).fetchall()
        item.messages=[ConversationMessageView(speaker=r['role'],text=r['content'],intent=r['intent'],timestamp=r['created_at']) for r in rows]
        return item
    def _row(self,r):
        state=_json(r['state_json'],{}); summary=_json(r['summary_json'],{})
        sources=[]
        for s in summary.get('sources',state.get('knowledge_sources',[])) or []:
            if not s.get('document_id') and not s.get('dokument_id'): continue
            sources.append(KnowledgeSourceView(document_id=str(s.get('document_id',s.get('dokument_id'))),filename=s.get('filename',s.get('dateiname','')),relative_path=s.get('relative_path',s.get('relativer_pfad','')),document_type=s.get('document_type',''),page_or_slide=str(s.get('page',s.get('seite',''))) or None,section=str(s.get('section',s.get('abschnitt',''))) or None,chunk_preview=s.get('chunk_preview',s.get('textausschnitt','')),relevance_score=s.get('relevance_score',s.get('relevanz',0)),query=s.get('query',''),used_at=s.get('used_at')))
        start=datetime.fromisoformat(r['started_at'] or r['created_at']); end=datetime.fromisoformat(r['ended_at']) if r['ended_at'] else None
        score=summary.get('lead_score',state.get('lead_score',0)); score=score.get('score',0) if isinstance(score,dict) else score or 0
        return ConversationOverview(session_id=r['session_id'],status=r['status'],started_at=start,ended_at=end,duration_seconds=max(0,(end-start).total_seconds()) if end else 0,name=state.get('name'),phone=r['caller_phone'] or state.get('phone'),conversation_type=r['direction'] or 'inbound',intent=summary.get('intent'),confidence=summary.get('confidence'),lead_score=score,escalation_status='open' if state.get('escalation') else None,appointment_status='open' if state.get('appointment') else None,followup_status=summary.get('followup_status'),summary=summary.get('summary') or summary.get('conversation_summary'),next_action=summary.get('next_action'),workflow_id=r['workflow_id'],knowledge_sources=sources)
