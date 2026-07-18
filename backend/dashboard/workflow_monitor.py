from __future__ import annotations
import json, sqlite3
from pathlib import Path
from .models import WorkflowOverview, WorkflowStepView

class WorkflowMonitor:
    def __init__(self,database_path:str|Path): self.database_path=Path(database_path)
    def _connect(self): db=sqlite3.connect(self.database_path); db.row_factory=sqlite3.Row; return db
    def list(self,*,date_from=None,date_to=None,status=None,workflow_type=None,search=None,limit=50,offset=0):
        if not self.database_path.exists(): return []
        clauses=[]; params=[]
        if date_from: clauses.append('i.created_at>=?'); params.append(date_from.isoformat())
        if date_to: clauses.append('i.created_at<=?'); params.append(date_to.isoformat())
        if status: clauses.append('i.status=?'); params.append(status)
        if workflow_type: clauses.append('(i.definition_id=? OR i.name=?)'); params += [workflow_type,workflow_type]
        if search: clauses.append("(i.workflow_id LIKE ? OR i.definition_id LIKE ? OR json_extract(i.input_payload,'$.lead_id') LIKE ?)"); params += [f'%{search}%']*3
        where=' WHERE '+' AND '.join(clauses) if clauses else ''
        sql='SELECT i.* FROM workflow_instances i'+where+' ORDER BY i.created_at DESC LIMIT ? OFFSET ?'
        try:
            with self._connect() as db: rows=db.execute(sql,(*params,limit,offset)).fetchall()
        except sqlite3.OperationalError: return []
        return [self._row(r,False) for r in rows]
    def get(self,workflow_id):
        if not self.database_path.exists(): return None
        try:
            with self._connect() as db: r=db.execute('SELECT * FROM workflow_instances WHERE workflow_id=?',(workflow_id,)).fetchone()
        except sqlite3.OperationalError: return None
        return self._row(r,True) if r else None
    def _row(self,r,details):
        steps=[]
        if details:
            with self._connect() as db: rows=db.execute('SELECT * FROM workflow_steps WHERE workflow_id=? ORDER BY position',(r['workflow_id'],)).fetchall()
            steps=[WorkflowStepView(step_id=x['step_id'],name=x['name'],status=x['status'],position=x['position'],agent=x['agent'],attempt=x['attempt'],max_retries=x['max_retries'],error=x['error'],started_at=x['started_at'],completed_at=x['completed_at']) for x in rows]
        inp=json.loads(r['input_payload'] or '{}'); meta=json.loads(r['metadata_payload'] or '{}')
        current=r['current_step_id']; ids=[x.step_id for x in steps]; idx=ids.index(current) if current in ids else -1
        return WorkflowOverview(workflow_id=r['workflow_id'],workflow_type=r['definition_id'],status=r['status'],current_step=current,previous_step=ids[idx-1] if idx>0 else None,next_step=ids[idx+1] if 0<=idx<len(ids)-1 else None,started_at=r['created_at'],updated_at=r['updated_at'],retry_count=sum(x.attempt for x in steps),waiting=r['status'] in ('waiting_for_approval','paused'),approval_status='pending' if r['approval_id'] else None,error=next((x.error for x in steps if x.error),None),session_id=meta.get('session_id'),lead_id=inp.get('lead_id'),steps=steps)
