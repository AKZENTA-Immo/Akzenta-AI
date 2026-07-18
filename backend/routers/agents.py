from fastapi import APIRouter, HTTPException

from backend.agents.core import AgentPermissionError
from backend.agents.manager import agent_manager
from backend.agents.services import (
    ApprovalAlreadyExecuted, ApprovalConflict, ApprovalExpired, ApprovalNotApproved,
    ApprovalNotFound, WorkflowIntegrityError, WorkflowNotFound,
)
from backend.agents.base_agent import AgentRequest, AgentResponse
from backend.agents.registry import agent_registry
from backend.agents.suite import register_default_agents
from backend.models.agent_models import (
    ApprovalCreateRequest, ApprovalDecisionRequest, ApprovalExecutionResponse, ApprovalRecord,
    ApprovalStatusResponse, CalendarSimulationRequest, CrmPreviewRequest, EmailDraftRequest,
    WorkflowCoreRequest, WorkflowCoreResponse,
)

router = APIRouter(prefix="/agents", tags=["Agenten"])
register_default_agents()


def _run(call):
    try:
        return call()
    except AgentPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (WorkflowNotFound, ApprovalNotFound) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ApprovalExpired as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except ApprovalNotApproved as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ApprovalConflict, ApprovalAlreadyExecuted, WorkflowIntegrityError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Die Agentenanfrage konnte nicht sicher verarbeitet werden.") from exc


@router.get("/status")
def statuses(): return {"agents": agent_manager.statuses(), "external_actions_enabled": False, **agent_manager.safety_status()}

@router.get("/approvals/status", response_model=ApprovalStatusResponse)
def approval_status(): return agent_manager.approvals.get_status()

@router.post("/approvals", response_model=ApprovalRecord)
def create_approval(request: ApprovalCreateRequest):
    return _run(lambda: agent_manager.approvals.create_approval(request.workflow_id, request.expires_in_minutes, request.requested_by))

@router.get("/approvals/{approval_id}", response_model=ApprovalRecord)
def get_approval(approval_id: str): return _run(lambda: agent_manager.approvals.get_approval(approval_id))

@router.post("/approvals/{approval_id}/decision", response_model=ApprovalRecord)
def decide_approval(approval_id: str, request: ApprovalDecisionRequest):
    return _run(lambda: agent_manager.approvals.decide_approval(approval_id, request.decision, request.decided_by, request.reason))

@router.post("/approvals/{approval_id}/execute", response_model=ApprovalExecutionResponse)
def execute_approval(approval_id: str): return _run(lambda: agent_manager.approvals.execute_approved_workflow(approval_id))

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

@router.get("/workflows/status")
def workflow_core_status(): return agent_manager.workflow_core.status()

@router.post("/workflows/core/run", response_model=WorkflowCoreResponse)
def workflow_core_run(request: WorkflowCoreRequest): return _run(lambda: agent_manager.workflow_core.run(request))

@router.post("/{agent_name}/execute", response_model=AgentResponse)
def direct_execute(agent_name: str, request: AgentRequest):
    if not agent_registry.has_agent(agent_name):
        raise HTTPException(status_code=404, detail="Unbekannter Agent.")
    return agent_registry.execute(agent_name, request)
