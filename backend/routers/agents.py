from fastapi import APIRouter, HTTPException

from backend.agents.core import AgentPermissionError
from backend.agents.manager import agent_manager
from backend.models.agent_models import CalendarSimulationRequest, CrmPreviewRequest, EmailDraftRequest

router = APIRouter(prefix="/agents", tags=["Agenten"])


def _run(call):
    try:
        return call()
    except AgentPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Die Agentenanfrage konnte nicht sicher verarbeitet werden.") from exc


@router.get("/status")
def statuses(): return {"agents": agent_manager.statuses(), "external_actions_enabled": False}

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
