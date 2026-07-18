import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.agents.agent_manager import AgentManagerRequest, CentralAgentManager

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

@pytest.mark.parametrize(("message", "agent"), [
    ("Ergänze den CRM Lead Max Mustermann", "crm"),
    ("Schreibe Frau Meier eine E-Mail", "email"),
    ("Plane morgen einen Termin für 45 Minuten", "kalender"),
    ("Formuliere eine WhatsApp Antwort", "whatsapp"),
    ("Erstelle einen Gesprächsleitfaden für den Rückruf", "telefon"),
    ("Erstelle eine Instagram Marketing Kampagne", "marketing"),
    ("Finde das Dokument in der Wissensbasis", "dokumente"),
    ("Schreibe einen Exposétext für ein Haus", "immobilien_text"),
    ("Hilf mir bei einer allgemeinen Frage", "allgemein"),
])
def test_execute_all_agents_safely(message, agent):
    response = client.post("/agent-manager/execute", json={"message": message})
    assert response.status_code == 200
    body = response.json()
    assert body["agent"] == agent
    assert body["status"] == "simulated"
    assert body["simulation"] is True
    assert body["approval_required"] is True
    assert body["proposed_actions"]
    assert any("Simulation" in warning for warning in body["warnings"])
    assert body["result"].get("external_action_executed") is not True

def test_ambiguous_request_uses_priority_and_marks_uncertain():
    body = client.post("/agent-manager/execute", json={"message": "Schreibe eine E-Mail und plane einen Termin"}).json()
    assert body["agent"] == "email"
    assert body["uncertain"] is True
    assert body["confidence"] < 0.75
    assert "Prioritätsregel" in body["reasoning"]

def test_execute_blocks_simulation_false():
    body = client.post("/agent-manager/execute", json={"message": "Sende eine WhatsApp", "simulation": False}).json()
    assert body["status"] == "blocked"
    assert body["simulation"] is False
    assert body["result"]["external_action_executed"] is False

def test_agent_error_is_contained():
    class BrokenAgent:
        agent_name = "allgemein"
        def execute(self, message, decision):
            raise RuntimeError(r"C:\secret\token.txt")
    manager = CentralAgentManager(agents={"allgemein": BrokenAgent()})
    result = manager.execute(AgentManagerRequest(message="Unbekanntes Anliegen"))
    assert result.status == "error"
    assert "C:\\" not in " ".join(result.warnings)
    assert result.result["external_action_executed"] is False
