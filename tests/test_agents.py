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
    assert {item["agent"] for item in body["agents"]} == {"crm", "email", "calendar"}
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
