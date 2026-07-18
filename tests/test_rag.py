import sqlite3
from backend import config
from backend.agents.workflow_engine import WorkflowOrchestrator
from backend.agents.workflow_repository import WorkflowRepository
from backend.agents.services import ApprovalService
from backend.models.agent_models import WorkflowStartRequest
from backend.rag.chunker import chunk_document
from backend.rag.knowledge_service import KnowledgeService, NOT_FOUND
from backend.rag.loader import load_document
from backend.rag.vector_store import VectorStore

class FakeEmbeddings:
    modell = "local-test"
    def embed(self, texts): return [self.embed_one(t) for t in texts]
    def embed_one(self, text): return [float("hamburg" in text.casefold()), float("berlin" in text.casefold()), .1]

class FakeChat:
    modell = "local-chat-test"
    def antworte(self, system, prompt): return "Die Information steht in Hamburg. [Quelle 1]"

def service(tmp_path): return KnowledgeService(VectorStore(tmp_path / "rag.sqlite3"), FakeEmbeddings(), FakeChat())

def test_dokument_laden_und_chunking(tmp_path, monkeypatch):
    dropbox = tmp_path / "Dropbox"; dropbox.mkdir()
    path = dropbox / "wissen.txt"; path.write_text("Hamburg.\n\n" + "Wissen " * 20, encoding="utf-8")
    monkeypatch.setattr(config, "DROPBOX_PATH", dropbox)
    document = load_document(path); chunks = chunk_document(document, 50, 10)
    assert document.filename == "wissen.txt" and len(chunks) > 1 and chunks[0].position == 0

def test_embedding_suche_mehrere_treffer_ask_und_persistenz(tmp_path, monkeypatch):
    dropbox = tmp_path / "Dropbox"; dropbox.mkdir()
    (dropbox / "a.txt").write_text("Hamburg Immobilienmarkt und Alster", encoding="utf-8")
    (dropbox / "b.txt").write_text("Hamburg Makler Wissen", encoding="utf-8")
    monkeypatch.setattr(config, "DROPBOX_PATH", dropbox)
    monkeypatch.setattr(config, "RAG_CHUNK_SIZE", 100); monkeypatch.setattr(config, "RAG_CHUNK_OVERLAP", 10)
    knowledge = service(tmp_path); result = knowledge.index()
    assert result["documents"] == 2 and result["embeddings"] == 2
    hits = knowledge.search("Hamburg", 5, 0)
    assert hits["count"] == 2 and hits["results"][0]["score"] >= hits["results"][1]["score"]
    answer = knowledge.ask("Was steht zu Hamburg?", 2)
    assert answer["answer"].endswith("[Quelle 1]") and answer["sources"]
    assert VectorStore(tmp_path / "rag.sqlite3").statistics() == knowledge.store.statistics()
    with sqlite3.connect(tmp_path / "rag.sqlite3") as db:
        assert {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")} >= {"documents", "chunks", "embeddings"}

def test_keine_treffer(tmp_path):
    assert service(tmp_path).ask("Unbekannt") == {"answer": NOT_FOUND, "sources": []}

def test_workflow_integration(tmp_path):
    knowledge = service(tmp_path); repo = WorkflowRepository(tmp_path / "workflow.sqlite3")
    orchestrator = WorkflowOrchestrator(repo, ApprovalService(repo), knowledge)
    workflow = orchestrator.start_workflow(WorkflowStartRequest(definition_id="lead_qualification", input={"name": "Test", "knowledge_query": "Hamburg"}))
    orchestrator.run_next_step(workflow.workflow_id); result = orchestrator.run_next_step(workflow.workflow_id)
    step = next(s for s in result.steps if s.step_id == "knowledge_lookup")
    assert step.status == "completed" and step.output["result"]["query"] == "Hamburg"
