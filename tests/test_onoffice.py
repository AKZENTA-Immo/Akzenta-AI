import requests
from fastapi.testclient import TestClient

from backend import config
from backend.agents.agent_manager import AgentManagerRequest, CentralAgentManager
from backend.integrations.onoffice.adapter import OnOfficeReadOnlyAdapter
from backend.integrations.onoffice.client import READ_ACTION, OnOfficeClient, create_hmac_v2
from backend.integrations.onoffice.exceptions import OnOfficeAuthenticationError, OnOfficeResponseError, OnOfficeTimeout
from backend.integrations.onoffice.models import OnOfficeSearchRequest
from backend.main import app


api = TestClient(app)


class Response:
    def __init__(self, body): self.body = body
    def raise_for_status(self): return None
    def json(self): return self.body


class Session:
    def __init__(self, body=None, error=None): self.body = body; self.error = error; self.calls = []
    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error: raise self.error
        return Response(self.body)


def result(records, total=None):
    return {"response": {"results": [{"status": {"errorcode": 0}, "data": {"records": records, "meta": {"cntabsolute": total if total is not None else len(records)}}}]}}


def configure_readonly(monkeypatch):
    monkeypatch.setattr(config, "ONOFFICE_ENABLED", True)
    monkeypatch.setattr(config, "ONOFFICE_MODE", "readonly")
    monkeypatch.setattr(config, "ONOFFICE_API_TOKEN", "test-token")
    monkeypatch.setattr(config, "ONOFFICE_API_SECRET", "test-secret")


def test_hmac_version_2_fixed_vector():
    assert create_hmac_v2(1700000000, "test-token", "estate", READ_ACTION, "test-secret") == "NAnEggtL0h4Z/P6Be8hhwYV7wFI+KfSPW4CIOiKJkOU="


def test_configuration_without_credentials_is_safe(monkeypatch):
    monkeypatch.setattr(config, "ONOFFICE_ENABLED", False)
    monkeypatch.setattr(config, "ONOFFICE_MODE", "mock")
    monkeypatch.setattr(config, "ONOFFICE_API_TOKEN", "")
    monkeypatch.setattr(config, "ONOFFICE_API_SECRET", "")
    body = api.get("/integrations/onoffice/status").json()
    assert body["configured"] is False
    assert body["reachable"] is False
    assert "token" not in str(body).lower()
    assert "secret" not in str(body).lower()


def test_mock_mode_blocks_reads_without_network(monkeypatch):
    monkeypatch.setattr(config, "ONOFFICE_ENABLED", True)
    monkeypatch.setattr(config, "ONOFFICE_MODE", "mock")
    response = api.post("/integrations/onoffice/contacts/search", json={"filters": {"last_name": "Muster"}})
    assert response.status_code == 409


def test_contact_and_estate_search_enforce_pagination_and_mapping(monkeypatch):
    configure_readonly(monkeypatch)
    session = Session(result([{"id": 7, "elements": {"Id": 7, "Vorname": "Max", "Name": "Muster", "Mandantenfeld": "privat"}}], 31))
    adapter = OnOfficeReadOnlyAdapter(OnOfficeClient("https://example.invalid", "test-token", "test-secret", session=session, clock=lambda: 1700000000))
    response = adapter.search_contacts(OnOfficeSearchRequest(filters={"last_name": "Muster"}, limit=5, offset=10))
    assert response.total == 31 and response.limit == 5 and response.offset == 10
    assert response.records[0].data["first_name"] == "Max"
    assert response.records[0].unmapped_fields == ["Mandantenfeld"]
    parameters = session.calls[0][1]["json"]["request"]["actions"][0]["parameters"]
    assert parameters["listlimit"] == 5 and parameters["listoffset"] == 10
    assert parameters["filter"]["Name"][0] == {"op": "like", "val": "%Muster%"}

    estate_session = Session(result([{"id": 8, "elements": {"Id": 8, "objektnr_extern": "A-8", "ort": "Hamburg"}}]))
    estate_adapter = OnOfficeReadOnlyAdapter(OnOfficeClient("https://example.invalid", "test-token", "test-secret", session=estate_session))
    estate = estate_adapter.search_estates(OnOfficeSearchRequest(filters={"city": "Hamburg"}))
    assert estate.records[0].data == {"onoffice_id": 8, "external_number": "A-8", "city": "Hamburg"}


def test_limits_filters_and_ids_are_validated():
    assert api.post("/integrations/onoffice/contacts/search", json={"filters": {"city": "Hamburg"}, "limit": 26}).status_code == 422
    assert api.post("/integrations/onoffice/contacts/search", json={"filters": {}}).status_code == 422
    assert api.get("/integrations/onoffice/contacts/0").status_code == 422
    assert api.get("/integrations/onoffice/estates/-1").status_code == 422


def test_timeout_authentication_and_malformed_responses():
    timeout_client = OnOfficeClient("https://example.invalid", "t", "s", session=Session(error=requests.Timeout()))
    try: timeout_client.request(READ_ACTION, "address")
    except OnOfficeTimeout: pass
    else: raise AssertionError("Timeout wurde nicht kontrolliert behandelt")

    auth = Session({"response": {"results": [{"status": {"errorcode": 401, "message": "authentication failed"}}]}})
    try: OnOfficeClient("https://example.invalid", "t", "s", session=auth).request(READ_ACTION, "address")
    except OnOfficeAuthenticationError: pass
    else: raise AssertionError("Authentifizierungsfehler wurde nicht erkannt")

    malformed = Session({"unexpected": True})
    try: OnOfficeClient("https://example.invalid", "t", "s", session=malformed).request(READ_ACTION, "address")
    except OnOfficeResponseError: pass
    else: raise AssertionError("Fehlerhafte Antwort wurde nicht erkannt")


def test_agent_manager_crm_marks_source_and_read_only(monkeypatch):
    monkeypatch.setattr(config, "ONOFFICE_ENABLED", False)
    response = CentralAgentManager().execute(AgentManagerRequest(message="CRM Kontakt für Max Muster"))
    assert response.result["data_source"] == "Simulation"
    assert response.result["read_only"] is True
    assert response.result["facts_from_onoffice"] == []
    assert response.result["crm_changed"] is False
