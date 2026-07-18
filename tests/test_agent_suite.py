import pytest
from fastapi.testclient import TestClient

from backend.agents.base_agent import AgentRequest, BaseAgent
from backend.agents.registry import AgentRegistry, agent_registry
from backend.main import app

client = TestClient(app)


class TestAgent(BaseAgent):
    name, display_name, capabilities = "test", "Test-Agent", ("testen",)
    def detect_action(self, message): return "testen"
    def simulate(self, request, action): return {"value": request.message, "external_action_executed": False}


def test_base_agent_structured_response_and_safe_default():
    response = TestAgent().execute(AgentRequest(message="Test"))
    assert response.agent == "test" and response.action == "testen"
    assert response.status == "simulated" and response.simulation is True
    assert response.result["external_action_executed"] is False


def test_base_agent_blocks_non_simulated_mutation():
    response = TestAgent().execute(AgentRequest(message="Test", simulation=False))
    assert response.status == "rejected"
    assert response.result["external_action_executed"] is False


def test_registry_register_find_duplicate_unknown_and_health():
    registry = AgentRegistry(); agent = registry.register(TestAgent())
    assert registry.has_agent("test") and registry.get("test") is agent
    with pytest.raises(ValueError): registry.register(TestAgent())
    with pytest.raises(KeyError): registry.get("unknown")
    assert registry.health_check()["status"] == "ok"
    assert registry.execute("test", AgentRequest(message="Hallo")).status == "simulated"


@pytest.mark.parametrize(("name", "message", "action"), [
    ("crm", "Suche den Lead Max Müller", "lead_suchen"),
    ("crm", "Erstelle eine Wiedervorlage für Lead Max Müller", "wiedervorlage_vorbereiten"),
    ("crm", "Ergänze eine Notiz beim Lead Max Müller", "notiz_vorbereiten"),
    ("email", "Schreibe Herrn Müller eine Terminbestätigung per E-Mail", "terminbestaetigung"),
    ("email", "Formuliere eine freundliche Nachfassmail an Frau Meier", "nachfassmail"),
    ("kalender", "Plane Freitag um 14 Uhr eine Besichtigung", "besichtigung_planen"),
    ("kalender", "Verschiebe den Termin auf Montag um 10 Uhr", "termin_verschieben_vorbereiten"),
    ("dokumente", "Suche den Energieausweis", "energieausweis_suchen"),
    ("dokumente", "Finde den Grundriss", "grundriss_suchen"),
    ("immobilien", "Erstelle einen Exposétext für ein Haus", "expose_text"),
    ("immobilien", "Schreibe eine Lagebeschreibung für eine Wohnung in Hamburg", "lagebeschreibung"),
    ("marketing", "Erstelle einen Instagram Post", "social_media_post"),
    ("marketing", "Schreibe einen Newsletter", "newsletter"),
    ("marketing", "Erstelle ein Video-Script", "video_script"),
    ("telefon", "Erstelle einen Gesprächsleitfaden", "gespraechsleitfaden"),
    ("telefon", "Bereite eine Leadqualifizierung am Telefon vor", "lead_qualifizierung"),
    ("whatsapp", "Formuliere eine WhatsApp Terminbestätigung an Max", "terminbestaetigung"),
    ("whatsapp", "Erstelle eine WhatsApp Antwort an Max", "antwort_entwurf"),
    ("allgemein", "Erkläre mir den Ablauf", "erklaeren"),
])
def test_agents_detect_actions_and_simulate(name, message, action):
    response = agent_registry.execute(name, AgentRequest(message=message))
    assert response.action == action
    assert response.status in {"simulated", "confirmation_required"}
    assert response.result.get("external_action_executed") is False


def test_missing_information_is_reported_without_guessing():
    calendar = agent_registry.execute("kalender", AgentRequest(message="Plane einen Termin"))
    assert {"Datum", "Uhrzeit"}.issubset(calendar.missing_information)
    estate = agent_registry.execute("immobilien", AgentRequest(message="Erstelle einen Exposétext"))
    assert estate.missing_information
    assert estate.result["assumptions"] == []


def test_paths_and_agent_failures_are_sanitized():
    response = TestAgent().execute(AgentRequest(message=r"C:\Users\Intern\secret.txt"))
    assert "C:\\" not in str(response.model_dump())


def test_registry_api_endpoints_and_unknown_agent():
    listing = client.get("/agents")
    assert listing.status_code == 200 and len(listing.json()["agents"]) == 9
    assert client.get("/agents/health").json()["registry_status"] == "available"
    direct = client.post("/agents/marketing/execute", json={"message": "Erstelle einen Newsletter"})
    assert direct.status_code == 200 and direct.json()["action"] == "newsletter"
    assert client.post("/agents/unknown/execute", json={"message": "Test"}).status_code == 404


def test_all_capabilities_are_declared_and_external_actions_stay_disabled():
    for status in agent_registry.list_agents():
        assert status["capabilities"]
        assert status["simulation"] is True
        result = agent_registry.execute(status["name"], AgentRequest(message="Bitte vorbereiten", simulation=False))
        if status["name"] not in {"dokumente", "allgemein"}:
            assert result.status == "rejected"
            assert result.result["external_action_executed"] is False
