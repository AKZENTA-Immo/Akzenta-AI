from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.adapters.providers import MockGmailAdapter, ProviderNotConnected
from backend.main import app
from backend.agents.manager import agent_manager


client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AGENT_AUDIT_LOG", tmp_path / "audit.jsonl")
    with agent_manager.approvals._lock:
        agent_manager.approvals._workflows.clear()
        agent_manager.approvals._approvals.clear()


def prepare_workflow(lead_id="LEAD-APPROVAL"):
    response = client.post("/agents/workflows/core/run", json={"lead_id": lead_id, "recipient_name": "Testperson", "target_group": "buyer", "purpose": "Sicheren Ablauf prüfen"})
    assert response.status_code == 200
    return response.json()


def create_approval(workflow_id):
    response = client.post("/agents/approvals", json={"workflow_id": workflow_id, "expires_in_minutes": 30, "requested_by": "steli"})
    assert response.status_code == 200
    return response.json()


def test_all_agents_are_safe_and_disconnected():
    response = client.get("/agents/status")
    assert response.status_code == 200
    body = response.json()
    assert body["external_actions_enabled"] is False
    assert {item["agent"] for item in body["agents"]} == {"crm", "email", "calendar", "workflow_core"}
    assert all(not item["provider_connected"] for item in body["agents"])
    assert all(not item["external_actions_enabled"] for item in body["agents"])


def test_crm_preview_never_changes_provider():
    response = client.post("/agents/crm/preview", json={"contact_reference": "TEST-001", "target_group": "seller", "note": "Rückruf gewünscht"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert body["approval"]["required"] is True
    assert body["external_action_executed"] is False


def test_email_is_draft_only():
    response = client.post("/agents/email/draft", json={"recipient_name": "Testperson", "target_group": "buyer", "purpose": "Information zum weiteren Ablauf", "facts": ["Besichtigung wird intern abgestimmt"]})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "draft"
    assert "Testperson" in body["output"]["body"]
    assert body["external_action_executed"] is False


def test_calendar_is_simulation_only():
    response = client.post("/agents/calendar/simulate", json={"attendee_name": "Testperson", "purpose": "Erstgespräch", "preferred_start": "2026-07-20T10:00:00+02:00", "duration_minutes": 45})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "simulation"
    assert body["output"]["availability_checked"] is False
    assert body["external_action_executed"] is False


def test_workflow_core_status_is_safe():
    response = client.get("/agents/workflows/status")
    assert response.status_code == 200
    body = response.json()
    assert body["agent"] == "workflow_core"
    assert body["provider"] == "internal"
    assert body["provider_connected"] is False
    assert body["external_actions_enabled"] is False


def test_workflow_core_runs_safe_multi_step_flow():
    response = client.post("/agents/workflows/core/run", json={
        "lead_id": "LEAD-170",
        "recipient_name": "Testperson",
        "target_group": "buyer",
        "purpose": "Abstimmung zum weiteren Ablauf",
        "simulate_calendar": True,
        "preferred_start": "2026-07-20T10:00:00+02:00",
        "duration_minutes": 45,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["external_action_executed"] is False
    assert body["workflow_id"].startswith("wf_")
    assert body["approval_required"] is True
    assert body["approval_status"] == "pending"
    assert len(body["workflow_fingerprint"]) == 64
    assert [step["step"] for step in body["steps"]] == ["crm_preview", "email_draft", "calendar_simulation"]
    assert all(step["external_action_executed"] is False for step in body["steps"])

    crm_step, email_step, calendar_step = body["steps"]
    assert crm_step["status"] == "blocked"
    assert crm_step["output"]["read_only"] is True
    assert email_step["status"] == "draft"
    assert "Testperson" in email_step["output"]["body"]
    assert calendar_step["status"] == "simulation"
    assert calendar_step["output"]["availability_checked"] is False


def test_workflow_core_without_calendar_has_only_preview_and_draft():
    response = client.post("/agents/workflows/core/run", json={
        "lead_id": "LEAD-171",
        "recipient_name": "Testperson",
        "target_group": "seller",
        "purpose": "Rückmeldung zur Immobilie",
    })
    assert response.status_code == 200
    assert [step["step"] for step in response.json()["steps"]] == ["crm_preview", "email_draft"]


def test_workflow_core_requires_start_for_calendar_simulation():
    response = client.post("/agents/workflows/core/run", json={
        "lead_id": "LEAD-172",
        "recipient_name": "Testperson",
        "target_group": "investor",
        "purpose": "Terminabstimmung",
        "simulate_calendar": True,
    })
    assert response.status_code == 422


def test_global_agent_status_includes_safe_workflow_core():
    response = client.get("/agents/status")
    assert response.json()["safe"] is True
    assert response.json()["external_actions"] is False
    assert response.json()["approval_required"] is True
    assert response.json()["execution_mode"] == "simulation"
    assert response.json()["persistence"] == "in_memory"
    workflow = next(item for item in response.json()["agents"] if item["agent"] == "workflow_core")
    assert workflow["provider_connected"] is False
    assert workflow["external_actions_enabled"] is False


def test_approval_status_is_safe_and_in_memory():
    body = client.get("/agents/approvals/status").json()
    assert body["enabled"] is True and body["mode"] == "simulation"
    assert body["persistent"] is False and body["external_actions_allowed"] is False
    assert set(body["supported_statuses"]) == {"pending", "approved", "rejected", "expired", "executed"}


def test_unknown_workflow_and_request_validation_are_rejected():
    assert client.post("/agents/approvals", json={"workflow_id": "wf_missing"}).status_code == 404
    assert client.post("/agents/approvals", json={}).status_code == 422
    assert client.post("/agents/approvals", json={"workflow_id": "  "}).status_code == 422
    assert client.post("/agents/approvals", json={"workflow_id": "wf_missing", "expires_in_minutes": 0}).status_code == 422
    assert client.post("/agents/approvals", json={"workflow_id": "wf_missing", "expires_in_minutes": 1441}).status_code == 422


def test_approval_lifecycle_executes_only_once_in_simulation():
    approval = create_approval(prepare_workflow()["workflow_id"])
    assert approval["status"] == "pending"
    assert client.post(f"/agents/approvals/{approval['approval_id']}/execute").status_code == 403
    decision = client.post(f"/agents/approvals/{approval['approval_id']}/decision", json={"decision": "approved", "decided_by": "steli", "reason": "Entwurf geprüft"})
    assert decision.status_code == 200 and decision.json()["status"] == "approved"
    execution = client.post(f"/agents/approvals/{approval['approval_id']}/execute")
    body = execution.json()
    assert execution.status_code == 200 and body["status"] == "executed"
    assert body["execution_mode"] == "simulation" and body["external_actions_performed"] is False and body["safe"] is True
    assert body["executed_steps"] == ["crm_preview", "email_draft"]
    assert client.post(f"/agents/approvals/{approval['approval_id']}/execute").status_code == 409


def test_rejected_approval_cannot_execute_or_change_again():
    approval = create_approval(prepare_workflow()["workflow_id"])
    decision = client.post(f"/agents/approvals/{approval['approval_id']}/decision", json={"decision": "rejected", "reason": "Überarbeiten"})
    assert decision.status_code == 200 and decision.json()["status"] == "rejected"
    assert client.post(f"/agents/approvals/{approval['approval_id']}/execute").status_code == 403
    assert client.post(f"/agents/approvals/{approval['approval_id']}/decision", json={"decision": "approved"}).status_code == 409
    assert client.post(f"/agents/approvals/{approval['approval_id']}/decision", json={"decision": "invalid"}).status_code == 422


def test_expired_approval_cannot_be_decided_or_executed():
    approval = create_approval(prepare_workflow()["workflow_id"])
    stored = agent_manager.approvals._approvals[approval["approval_id"]]
    stored.expires_at = stored.created_at
    assert client.post(f"/agents/approvals/{approval['approval_id']}/decision", json={"decision": "approved"}).status_code == 410
    assert client.post(f"/agents/approvals/{approval['approval_id']}/execute").status_code == 410
    assert client.get(f"/agents/approvals/{approval['approval_id']}").json()["status"] == "expired"


def test_workflow_fingerprint_tampering_blocks_execution():
    workflow = prepare_workflow()
    approval = create_approval(workflow["workflow_id"])
    assert client.post(f"/agents/approvals/{approval['approval_id']}/decision", json={"decision": "approved"}).status_code == 200
    agent_manager.approvals._workflows[workflow["workflow_id"]].steps[0].output["note_preview"] = "manipuliert"
    assert client.post(f"/agents/approvals/{approval['approval_id']}/execute").status_code == 409
    assert client.get(f"/agents/approvals/{approval['approval_id']}").json()["status"] == "approved"


def test_approval_cannot_be_reassigned_to_another_workflow():
    first, second = prepare_workflow("LEAD-FIRST"), prepare_workflow("LEAD-SECOND")
    approval = create_approval(first["workflow_id"])
    assert client.post(f"/agents/approvals/{approval['approval_id']}/decision", json={"decision": "approved"}).status_code == 200
    agent_manager.approvals._approvals[approval["approval_id"]].workflow_id = second["workflow_id"]
    assert client.post(f"/agents/approvals/{approval['approval_id']}/execute").status_code == 409


def test_viewer_cannot_create_drafts():
    response = client.post("/agents/email/draft", json={"context": {"actor_id": "test-viewer", "role": "viewer"}, "recipient_name": "Testperson", "target_group": "investor", "purpose": "Unterlagen"})
    assert response.status_code == 403


def test_mock_adapter_blocks_execution():
    with pytest.raises(ProviderNotConnected):
        MockGmailAdapter().execute({"to": "nobody@example.invalid"})


def test_prompts_are_versioned_files():
    for agent in ("crm", "email", "calendar"):
        path = config.PROJECT_PATH / "backend" / "prompts" / agent / "v1.md"
        assert path.is_file()
        assert "niemals" in path.read_text(encoding="utf-8").lower()
