import os
from pathlib import Path

os.environ["AKZENTA_WORKFLOW_DB"] = str(Path(__file__).resolve().parent.parent / ".tmp" / "pytest-import-engine.sqlite3")

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.main import app
from backend.agents.manager import agent_manager
from backend.agents.services import ApprovalService
from backend.agents.workflow_engine import WorkflowOrchestrator
from backend.agents.workflow_repository import WorkflowRepository
from backend.models.agent_models import WorkflowDefinition, WorkflowStepDefinition

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_engine(tmp_path):
    repository = WorkflowRepository(tmp_path / "engine.sqlite3")
    agent_manager.repository = repository
    agent_manager.approvals = ApprovalService(repository)
    agent_manager.workflow_core.approvals = agent_manager.approvals
    agent_manager.workflow_engine = WorkflowOrchestrator(repository, agent_manager.approvals)


def start(definition="lead_qualification", **input_data):
    data = {"name":"Max Mustermann", "email":"max@example.de", "object_address":"Musterstraße 12", "appointment_requested":True, **input_data}
    response = client.post("/agents/workflows/start", json={"definition_id":definition,"input":data,"requested_by":"tester"})
    assert response.status_code == 200
    return response.json()


def test_engine_status_and_registered_definitions_are_safe():
    status = client.get("/agents/workflow-engine/status").json()
    assert status["safe"] and status["simulation_only"] and not status["external_actions_allowed"]
    assert status["retry_enabled"] and status["resume_enabled"]
    assert {d["definition_id"] for d in client.get("/agents/workflow-definitions").json()} == {"lead_qualification","seller_follow_up"}
    assert client.get("/agents/workflow-definitions/missing").status_code == 404


def test_definition_graph_validation_rejects_duplicates_unknown_and_cycles():
    base = dict(name="x",agent="workflow",action="finalize")
    with pytest.raises(ValidationError): WorkflowDefinition(definition_id="x",name="x",steps=[WorkflowStepDefinition(step_id="a",**base),WorkflowStepDefinition(step_id="a",**base)])
    with pytest.raises(ValidationError): WorkflowDefinition(definition_id="x",name="x",steps=[WorkflowStepDefinition(step_id="a",depends_on=["missing"],**base)])
    with pytest.raises(ValidationError): WorkflowDefinition(definition_id="x",name="x",steps=[WorkflowStepDefinition(step_id="a",depends_on=["b"],**base),WorkflowStepDefinition(step_id="b",depends_on=["a"],**base)])


def test_run_stops_at_approval_and_persists_steps():
    workflow = start(); result = client.post(f"/agents/workflows/{workflow['workflow_id']}/run").json()
    assert result["status"] == "waiting_for_approval" and result["approval_id"]
    states = {s["step_id"]:s["status"] for s in result["steps"]}
    assert states["approval_gate"] == "waiting" and states["simulated_execution"] == "pending"
    assert WorkflowOrchestrator(WorkflowRepository(agent_manager.repository.database_path), ApprovalService(WorkflowRepository(agent_manager.repository.database_path))).get_workflow(workflow["workflow_id"]).approval_id == result["approval_id"]


def test_pending_rejected_and_approved_resume_rules():
    workflow = start(); waiting = client.post(f"/agents/workflows/{workflow['workflow_id']}/run").json()
    assert client.post(f"/agents/workflows/{workflow['workflow_id']}/resume",json={}).status_code == 403
    client.post(f"/agents/approvals/{waiting['approval_id']}/decision",json={"decision":"rejected"})
    assert client.post(f"/agents/workflows/{workflow['workflow_id']}/resume",json={}).status_code == 403
    approved = start(name="Erika"); waiting = client.post(f"/agents/workflows/{approved['workflow_id']}/run").json()
    client.post(f"/agents/approvals/{waiting['approval_id']}/decision",json={"decision":"approved"})
    done = client.post(f"/agents/workflows/{approved['workflow_id']}/resume",json={"actor":"tester"})
    assert done.status_code == 200 and done.json()["status"] == "completed"
    assert client.post(f"/agents/workflows/{approved['workflow_id']}/run").status_code == 409


def test_conditions_skip_calendar_and_all_outputs_are_simulations():
    workflow = start(appointment_requested=False)
    waiting = client.post(f"/agents/workflows/{workflow['workflow_id']}/run").json()
    calendar = next(s for s in waiting["steps"] if s["step_id"] == "calendar_preview")
    assert calendar["status"] == "skipped"
    for step in waiting["steps"]:
        if step["status"] == "completed":
            assert step["output"]["simulation"] is True and step["output"]["external_actions_performed"] is False


def test_failure_retry_attempt_and_cancel_guards():
    workflow = start(name=None)
    failed = client.post(f"/agents/workflows/{workflow['workflow_id']}/run").json()
    assert failed["status"] == "failed" and failed["steps"][0]["attempt"] == 1
    retried = client.post(f"/agents/workflows/{workflow['workflow_id']}/retry",json={"step_id":"validate_lead"})
    assert retried.status_code == 200 and retried.json()["steps"][0]["attempt"] == 2
    assert client.post(f"/agents/workflows/{workflow['workflow_id']}/retry",json={"step_id":"crm_lookup"}).status_code == 409
    other = start(name="Cancel"); assert client.post(f"/agents/workflows/{other['workflow_id']}/cancel",json={}).json()["status"] == "cancelled"
    assert client.post(f"/agents/workflows/{other['workflow_id']}/run").status_code == 409


def test_audit_is_chronological_and_complete():
    workflow = start(); waiting = client.post(f"/agents/workflows/{workflow['workflow_id']}/run").json()
    client.post(f"/agents/approvals/{waiting['approval_id']}/decision",json={"decision":"approved"})
    client.post(f"/agents/workflows/{workflow['workflow_id']}/resume",json={})
    events = client.get(f"/agents/workflows/{workflow['workflow_id']}/audit").json()
    kinds = {e["event_type"] for e in events}
    assert {"workflow_step_started","workflow_step_completed","workflow_waiting_for_approval","workflow_resumed","workflow_completed"} <= kinds
    assert [e["created_at"] for e in events] == sorted(e["created_at"] for e in events)
