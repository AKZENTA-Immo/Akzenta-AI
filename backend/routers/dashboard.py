from __future__ import annotations
from datetime import date,datetime,time,timezone
from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException,Query,Request
from fastapi.responses import StreamingResponse
from backend import config
from backend.dashboard.agent_status_service import AgentStatusService
from backend.dashboard.conversation_monitor import ConversationMonitor
from backend.dashboard.dashboard_service import DashboardService
from backend.dashboard.event_service import EventService
from backend.dashboard.lead_monitor import LeadMonitor
from backend.dashboard.statistics_service import StatisticsService
from backend.dashboard.workflow_monitor import WorkflowMonitor

router=APIRouter(prefix='/dashboard',tags=['Operator Dashboard'])
Limit=Annotated[int,Query(ge=1,le=500)]; Offset=Annotated[int,Query(ge=0,le=1_000_000)]
def get_services(request:Request):
    services=getattr(request.app.state,'dashboard_services',None)
    if services is None:
        c=ConversationMonitor(config.PHONE_DB_PATH); w=WorkflowMonitor(config.WORKFLOW_DB_PATH); l=LeadMonitor(c); e=EventService(config.DASHBOARD_DB_PATH); a=AgentStatusService(config.PHONE_DB_PATH,config.WORKFLOW_DB_PATH,config.RAG_DB_PATH,config.DASHBOARD_DB_PATH); s=StatisticsService(c,w,l); services={'conversations':c,'workflows':w,'leads':l,'events':e,'agents':a,'statistics':s,'dashboard':DashboardService(c,w,l,a,e)}; request.app.state.dashboard_services=services
    return services
def dates(date_from:date|None,date_to:date|None):
    if date_from and date_to and date_from>date_to: raise HTTPException(422,'date_from darf nicht nach date_to liegen.')
    return datetime.combine(date_from,time.min,tzinfo=timezone.utc) if date_from else None,datetime.combine(date_to,time.max,tzinfo=timezone.utc) if date_to else None
@router.get('/overview')
def overview(s=Depends(get_services)): return s['dashboard'].overview()
@router.get('/conversations')
def conversations(date_from:date|None=None,date_to:date|None=None,status:str|None=None,search:Annotated[str|None,Query(max_length=200)]=None,limit:Limit=50,offset:Offset=0,s=Depends(get_services)): a,b=dates(date_from,date_to); return s['conversations'].list(date_from=a,date_to=b,status=status,search=search,limit=limit,offset=offset)
@router.get('/conversations/{session_id}')
def conversation(session_id:str,s=Depends(get_services)):
    item=s['conversations'].get(session_id)
    if not item: raise HTTPException(404,'Telefonsitzung nicht gefunden.')
    return item
@router.get('/statistics')
def statistics(date_from:date|None=None,date_to:date|None=None,s=Depends(get_services)): a,b=dates(date_from,date_to); return s['statistics'].calculate(a,b)
@router.get('/workflows')
def workflows(date_from:date|None=None,date_to:date|None=None,status:str|None=None,workflow_type:str|None=None,search:Annotated[str|None,Query(max_length=200)]=None,limit:Limit=50,offset:Offset=0,s=Depends(get_services)): a,b=dates(date_from,date_to); return s['workflows'].list(date_from=a,date_to=b,status=status,workflow_type=workflow_type,search=search,limit=limit,offset=offset)
@router.get('/workflows/{workflow_id}')
def workflow(workflow_id:str,s=Depends(get_services)):
    item=s['workflows'].get(workflow_id)
    if not item: raise HTTPException(404,'Workflow nicht gefunden.')
    return item
@router.get('/leads')
def leads(date_from:date|None=None,date_to:date|None=None,status:str|None=None,lead_type:str|None=None,search:Annotated[str|None,Query(max_length=200)]=None,limit:Limit=50,offset:Offset=0,s=Depends(get_services)): a,b=dates(date_from,date_to); return s['leads'].list(date_from=a,date_to=b,status=status,lead_type=lead_type,search=search,limit=limit,offset=offset)
@router.get('/agents')
def agents(agent:str|None=None,s=Depends(get_services)): return s['agents'].list(agent)
@router.get('/events')
def events(date_from:date|None=None,date_to:date|None=None,limit:Limit=50,offset:Offset=0,s=Depends(get_services)): a,b=dates(date_from,date_to); return s['events'].list_events(date_from=a,date_to=b,limit=limit,offset=offset)
@router.get('/events/stream',responses={200:{'content':{'text/event-stream':{}}}})
def event_stream(s=Depends(get_services)): return StreamingResponse(s['events'].stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})
@router.get('/notifications')
def notifications(limit:Limit=50,offset:Offset=0,s=Depends(get_services)): return s['events'].list_notifications(limit,offset)
