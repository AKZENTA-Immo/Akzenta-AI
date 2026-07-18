import sqlite3
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.agents.manager import AgentManager
from backend.agents.services import ApprovalService
from backend.agents.workflow_engine import WorkflowOrchestrator
from backend.agents.workflow_repository import WorkflowRepository
from backend.main import app
from backend.phone.call_manager import CallManager, PhoneEndRequest, PhoneMessageRequest, PhoneSessionClosed, PhoneStartRequest
from backend.phone.call_summary import LeadScore
from backend.phone.conversation_memory import ConversationMemory


class FakeKnowledgeService:
    def ask(self, question, top_k=None):
        if "kaufpreis" in question.casefold(): return {"answer": "Der Kaufpreis beträgt 500.000 Euro. [Quelle 1]", "sources": [{"number": 1}]}
        return {"answer": "Keine passende Information gefunden.", "sources": []}


class FakeSTT:
    def transcribe(self, audio, *, language="de"): return "Hallo"


class FakeTTS:
    def synthesize(self, text, *, language="de"): return b"lokales-audio"


@pytest.fixture
def manager(tmp_path):
    repository = WorkflowRepository(tmp_path / "workflow.sqlite3")
    agents = AgentManager(repository)
    agents.workflow_engine = WorkflowOrchestrator(repository, ApprovalService(repository), FakeKnowledgeService())
    memory = ConversationMemory(tmp_path / "phone.sqlite3")
    return CallManager(memory=memory, knowledge_service=FakeKnowledgeService(), agent_manager=agents)


def test_start_dialog_workflow_and_persistence(manager):
    started = manager.start(PhoneStartRequest(phone="040 123456", name="Max Muster"))
    assert started["status"] == "active" and started["workflow_id"].startswith("wfi_")
    reply = manager.message(PhoneMessageRequest(session_id=started["session_id"], message="Hallo, ich suche eine Wohnung"))
    assert reply["intent"] == "objektfrage" and reply["state"]["name"] == "Max Muster"
    session = manager.session(started["session_id"])
    assert len(session["messages"]) == 3 and session["workflow_id"] == started["workflow_id"]


def test_knowledge_lookup_and_secure_fallback(manager):
    session_id = manager.start(PhoneStartRequest())["session_id"]
    known = manager.message(PhoneMessageRequest(session_id=session_id, message="Wie hoch ist der Kaufpreis?"))
    unknown = manager.message(PhoneMessageRequest(session_id=session_id, message="Welche Finanzierung ist garantiert?"))
    assert "500.000" in known["message"]
    assert unknown["message"] == "Darauf habe ich aktuell keine gesicherte Information."


def test_appointment_is_stored_locally(manager):
    session_id = manager.start(PhoneStartRequest(name="Eva Test"))["session_id"]
    start = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    result = manager.message(PhoneMessageRequest(session_id=session_id, message="Ich möchte einen Termin", appointment_start=start))
    assert result["appointment"]["provider"] == "local" and result["appointment"]["status"] == "reserved_local"
    with manager.memory._connect() as db: assert db.execute("SELECT COUNT(*) FROM appointments").fetchone()[0] == 1


def test_escalation(manager):
    session_id = manager.start(PhoneStartRequest())["session_id"]
    result = manager.message(PhoneMessageRequest(session_id=session_id, message="Ich möchte mit einem Mitarbeiter sprechen"))
    assert result["escalation"] == "Mitarbeiter angefordert"


def test_end_creates_summary_crm_email_and_completes_workflow(manager):
    session_id = manager.start(PhoneStartRequest(phone="040123456", name="Ada Beispiel"))["session_id"]
    manager.message(PhoneMessageRequest(session_id=session_id, message="Mein Budget ist maximal 600000 Euro und ich möchte eine Besichtigung"))
    result = manager.end(PhoneEndRequest(session_id=session_id, create_email_draft=True))
    summary = result["summary"]
    assert summary["lead_score"] >= 40
    assert summary["crm_update"]["agent"] == "crm"
    assert summary["email_draft"]["status"] == "draft"
    assert summary["workflow_status"] == "completed"
    assert manager.session(session_id)["summary"]["next_steps"]


def test_lead_score_parameters():
    state = {"budget": "500000", "appointment": "morgen", "interest": "kapitalanlage", "property": "Wohnung"}
    assert LeadScore.calculate(state) == 85
    assert LeadScore.calculate({}) == 0


def test_tables_statistics_and_error_cases(manager):
    with sqlite3.connect(manager.memory.database_path) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"calls", "call_messages", "call_summary", "phone_sessions"} <= tables
    session_id = manager.start(PhoneStartRequest())["session_id"]
    manager.end(PhoneEndRequest(session_id=session_id))
    assert manager.statistics()["completed_sessions"] == 1
    with pytest.raises(PhoneSessionClosed): manager.message(PhoneMessageRequest(session_id=session_id, message="Hallo"))


def test_phone_api(manager):
    app.state.call_manager = manager
    client = TestClient(app)
    started = client.post("/phone/start", json={"name": "API Test"})
    assert started.status_code == 200
    session_id = started.json()["session_id"]
    assert client.post("/phone/message", json={"session_id": session_id, "message": "Hallo"}).status_code == 200
    assert client.get(f"/phone/session/{session_id}").status_code == 200
    assert client.get("/phone/statistics").json()["calls"] >= 1
    assert client.post("/phone/end", json={"session_id": session_id}).status_code == 200
    assert client.get("/phone/session/nicht-vorhanden").status_code == 404


def test_exchangeable_stt_and_tts(manager):
    import base64
    audio_manager = CallManager(memory=manager.memory, knowledge_service=FakeKnowledgeService(), agent_manager=manager.agents,
                                stt_adapter=FakeSTT(), tts_adapter=FakeTTS())
    session_id = audio_manager.start(PhoneStartRequest())["session_id"]
    result = audio_manager.message(PhoneMessageRequest(session_id=session_id, audio_base64=base64.b64encode(b"audio").decode(), synthesize_audio=True))
    assert result["transcript"] == "Hallo"
    assert base64.b64decode(result["audio_base64"]) == b"lokales-audio"
