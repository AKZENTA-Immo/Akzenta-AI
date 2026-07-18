from fastapi import APIRouter, HTTPException

from backend.agents.agent_manager import AgentManagerRequest, AgentManagerResult, central_agent_manager

router = APIRouter(prefix="/agent-manager", tags=["Agent Manager"])

@router.post("/route", response_model=AgentManagerResult)
def route_agent(request: AgentManagerRequest) -> AgentManagerResult:
    try:
        return central_agent_manager.route(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Die Anfrage konnte nicht sicher zugeordnet werden.") from exc
