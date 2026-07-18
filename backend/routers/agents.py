from fastapi import APIRouter, HTTPException

from backend.agents.core import AgentPermissionError
from backend.agents.manager import agent_manager
from backend.agents.base_agent import AgentRequest, AgentResponse
from backend.agents.registry import agent_registry
from backend.agents.suite import register_default_agents
from backend.models.agent_models import CalendarSimulationRequest, CrmPreviewRequest, EmailDraftRequest

router = APIRouter(prefix="/agents", tags=["Agenten"])
register_default_agents()


def _run(call):
    try:
        return call()
    except AgentPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Die Agentenanfrage konnte nicht sicher verarbeitet werden.") from exc


@router.get("/status")
def statuses(): return {"agents": agent_manager.statuses(), "external_actions_enabled": False}

@router.get("")
def list_agents(): return {"agents": agent_registry.list_agents(), "external_actions_enabled": False}

@router.get("/health")
def agents_health(): return agent_registry.health_check()

@router.get("/crm/status")
def crm_status(): return agent_manager.crm.status()

@router.post("/crm/preview")
def crm_preview(request: CrmPreviewRequest): return _run(lambda: agent_manager.crm.preview(request))

@router.get("/email/status")
def email_status(): return agent_manager.email.status()

@router.post("/email/draft")
def email_draft(request: EmailDraftRequest): return _run(lambda: agent_manager.email.draft(request))

@router.get("/calendar/status")
def calendar_status(): return agent_manager.calendar.status()

@router.post("/calendar/simulate")
def calendar_simulate(request: CalendarSimulationRequest): return _run(lambda: agent_manager.calendar.simulate(request))

@router.post("/{agent_name}/execute", response_model=AgentResponse)
def direct_execute(agent_name: str, request: AgentRequest):
    if not agent_registry.has_agent(agent_name):
        raise HTTPException(status_code=404, detail="Unbekannter Agent.")
    return agent_registry.execute(agent_name, request)
