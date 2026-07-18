import json,sqlite3
from datetime import datetime,timezone
import pytest
from fastapi.testclient import TestClient
from backend.dashboard.agent_status_service import AgentStatusService
from backend.dashboard.conversation_monitor import ConversationMonitor
from backend.dashboard.dashboard_service import DashboardService
from backend.dashboard.event_service import EventService
from backend.dashboard.lead_monitor import LeadMonitor
from backend.dashboard.statistics_service import StatisticsService
from backend.dashboard.workflow_monitor import WorkflowMonitor
from backend.main import app

@pytest.fixture
def client(tmp_path):
    phone=tmp_path/'phone.sqlite3'; workflow=tmp_path/'workflow.sqlite3'; dashboard=tmp_path/'dashboard.sqlite3'; now=datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(phone) as db:
        db.executescript('CREATE TABLE phone_sessions(session_id TEXT PRIMARY KEY,status TEXT,state_json TEXT,workflow_id TEXT,created_at TEXT,updated_at TEXT);CREATE TABLE calls(call_id TEXT PRIMARY KEY,session_id TEXT,direction TEXT,caller_phone TEXT,started_at TEXT,ended_at TEXT);CREATE TABLE call_messages(message_id INTEGER PRIMARY KEY,session_id TEXT,role TEXT,content TEXT,intent TEXT,created_at TEXT);CREATE TABLE call_summary(session_id TEXT PRIMARY KEY,summary_json TEXT,created_at TEXT);CREATE TABLE appointments(appointment_id TEXT PRIMARY KEY,session_id TEXT,starts_at TEXT,duration_minutes INTEGER,status TEXT,details_json TEXT,created_at TEXT);')
        state=json.dumps({'name':'Max Muster','email':'max@example.test','property':'Wohnung','lead_score':72,'appointment':'requested'})
        db.execute('INSERT INTO phone_sessions VALUES(?,?,?,?,?,?)',('session-1','active',state,'wf-1',now,now));db.execute('INSERT INTO calls VALUES(?,?,?,?,?,?)',('call-1','session-1','inbound','040123456',now,None));db.execute('INSERT INTO call_messages VALUES(?,?,?,?,?,?)',(1,'session-1','caller','Guten Tag','objektfrage',now));db.execute('INSERT INTO call_summary VALUES(?,?,?)',('session-1',json.dumps({'summary':'Interesse','sources':[{'document_id':'doc-1','filename':'Expose.pdf','relevance_score':.9}]}),now))
    with sqlite3.connect(workflow) as db:
        db.executescript('CREATE TABLE workflow_instances(workflow_id TEXT PRIMARY KEY,definition_id TEXT,name TEXT,status TEXT,current_step_id TEXT,created_at TEXT,updated_at TEXT,completed_at TEXT,requested_by TEXT,input_payload TEXT,output_payload TEXT,approval_id TEXT,execution_mode TEXT,external_actions_performed INTEGER,metadata_payload TEXT);CREATE TABLE workflow_steps(workflow_id TEXT,step_id TEXT,position INTEGER,name TEXT,agent TEXT,action TEXT,status TEXT,attempt INTEGER,max_retries INTEGER,depends_on TEXT,condition_payload TEXT,input_payload TEXT,output_payload TEXT,error TEXT,started_at TEXT,completed_at TEXT,updated_at TEXT);')
        db.execute('INSERT INTO workflow_instances VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',('wf-1','lead_followup','Lead Follow-up','running','score',now,now,None,None,json.dumps({'lead_id':'lead-1'}),'{}',None,'simulation',0,json.dumps({'session_id':'session-1'})));db.execute('INSERT INTO workflow_steps VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',('wf-1','score',0,'Scoring','crm','score','running',1,2,'[]','{}','{}','{}',None,now,None,now))
    c=ConversationMonitor(phone);w=WorkflowMonitor(workflow);l=LeadMonitor(c);e=EventService(dashboard);a=AgentStatusService(phone,workflow,tmp_path/'knowledge.sqlite3',dashboard);s=StatisticsService(c,w,l)
    with e._connect() as db:
        db.execute('INSERT INTO dashboard_events VALUES(?,?,?,?,?,?,?,?,?)',('evt-1','conversation_started','info','Gespräch','Gestartet','conversation','session-1','{}',now));db.execute('INSERT INTO dashboard_notifications VALUES(?,?,?,?,?,?)',('note-1','Hinweis','Test','info',0,now))
    app.state.dashboard_services={'conversations':c,'workflows':w,'leads':l,'events':e,'agents':a,'statistics':s,'dashboard':DashboardService(c,w,l,a,e)}
    yield TestClient(app)
    delattr(app.state,'dashboard_services')

def test_dashboard_overview(client): assert client.get('/dashboard/overview').json()['active_conversations']==1
def test_conversations_list(client): assert client.get('/dashboard/conversations').json()[0]['session_id']=='session-1'
def test_conversation_detail(client): assert client.get('/dashboard/conversations/session-1').json()['messages'][0]['speaker']=='caller'
def test_workflow_list(client): assert client.get('/dashboard/workflows').json()[0]['workflow_id']=='wf-1'
def test_workflow_detail(client): assert client.get('/dashboard/workflows/wf-1').json()['steps'][0]['step_id']=='score'
def test_lead_list(client): assert client.get('/dashboard/leads').json()[0]['name']=='Max Muster'
def test_agent_status(client): assert len(client.get('/dashboard/agents').json())==8
def test_statistics(client): assert client.get('/dashboard/statistics').json()['conversations']==1
def test_date_filter(client): assert client.get('/dashboard/conversations?date_from=2099-01-01').json()==[]
def test_status_filter(client): assert client.get('/dashboard/conversations?status=completed').json()==[]
def test_search(client): assert len(client.get('/dashboard/conversations?search=040123').json())==1
def test_knowledge_sources(client): assert client.get('/dashboard/conversations/session-1').json()['knowledge_sources'][0]['document_id']=='doc-1'
def test_events(client): assert client.get('/dashboard/events').json()[0]['id']=='evt-1'
def test_notifications(client): assert client.get('/dashboard/notifications').json()[0]['id']=='note-1'
def test_sse_content_type(client): assert client.app.openapi()['paths']['/dashboard/events/stream']['get']['responses']['200']['content'].get('text/event-stream') is not None
@pytest.mark.parametrize('query',['limit=0','limit=501','offset=-1','date_from=no-date','date_from=2026-02-02&date_to=2026-01-01'])
def test_invalid_query_parameters(client,query): assert client.get('/dashboard/conversations?'+query).status_code==422
def test_unknown_session(client): assert client.get('/dashboard/conversations/missing').status_code==404
def test_unknown_workflow(client): assert client.get('/dashboard/workflows/missing').status_code==404
def test_sqlite_persistence(client): assert client.get('/dashboard/events').json()
def test_no_write_operations(client): assert all(not ({'POST','PUT','PATCH','DELETE'} & set(route.methods or [])) for route in client.app.routes if route.path.startswith('/dashboard'))

def test_empty_database(tmp_path):
    phone=tmp_path/'empty.sqlite3';
    with sqlite3.connect(phone) as db: db.executescript('CREATE TABLE phone_sessions(session_id TEXT,status TEXT,state_json TEXT,workflow_id TEXT,created_at TEXT,updated_at TEXT);CREATE TABLE calls(call_id TEXT,session_id TEXT,direction TEXT,caller_phone TEXT,started_at TEXT,ended_at TEXT);CREATE TABLE call_summary(session_id TEXT,summary_json TEXT,created_at TEXT);')
    assert ConversationMonitor(phone).list()==[]
