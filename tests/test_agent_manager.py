import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

@pytest.mark.parametrize(("message", "agent"), [
    ("Aktualisiere den CRM-Kontakt für diesen Lead", "crm"),
    ("Schreibe Herrn Müller eine E-Mail mit der Terminbestätigung", "email"),
    ("Plane einen Termin im Kalender für die Besichtigung", "kalender"),
    ("Suche das PDF in unserer Wissensbasis", "dokumente"),
    ("Erstelle einen Exposétext für diese Wohnung", "immobilien_text"),
    ("Wie kannst du mich heute unterstützen?", "allgemein"),
    ("Eine völlig unbekannte Anfrage ohne Fachbegriff", "allgemein"),
])
def test_routing_categories(message, agent):
    response = client.post("/agent-manager/route", json={"message": message})
    assert response.status_code == 200
    body = response.json()
    assert body["agent"] == agent
    assert body["original_message"] == message
    assert 0 <= body["confidence"] <= 1
    assert body["reason"]
    assert body["simulation"] is True
    assert body["result"] == {"status": "simulated", "external_action_executed": False}

def test_empty_message_is_rejected():
    response = client.post("/agent-manager/route", json={"message": "   "})
    assert response.status_code == 422

def test_simulation_defaults_to_enabled_and_execution_cannot_be_enabled():
    default = client.post("/agent-manager/route", json={"message": "CRM Kontakt"}).json()
    blocked = client.post("/agent-manager/route", json={"message": "CRM Kontakt", "simulation": False}).json()
    assert default["simulation"] is True
    assert blocked["simulation"] is False
    assert blocked["result"]["status"] == "blocked"
    assert blocked["result"]["external_action_executed"] is False

def test_internal_errors_do_not_expose_absolute_paths(monkeypatch):
    def fail(_request):
        raise RuntimeError(r"C:\Users\Intern\secret.txt")
    monkeypatch.setattr("backend.routers.agent_manager.central_agent_manager.route", fail)
    response = client.post("/agent-manager/route", json={"message": "CRM Kontakt"})
    assert response.status_code == 500
    assert "C:\\" not in response.text
    assert "secret.txt" not in response.text
