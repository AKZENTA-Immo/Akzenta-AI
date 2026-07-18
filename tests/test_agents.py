from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.adapters.providers import MockGmailAdapter, ProviderNotConnected
from backend.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AGENT_AUDIT_LOG", tmp_path / "audit.jsonl")


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
    workflow = next(item for item in response.json()["agents"] if item["agent"] == "workflow_core")
    assert workflow["provider_connected"] is False
    assert workflow["external_actions_enabled"] is False


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
