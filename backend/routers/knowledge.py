from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.rag.embedding import EmbeddingFehler
from backend.rag.knowledge_service import KnowledgeService
from backend.services.dokument_scanner import DokumentPfadFehler
from backend.services.ollama_chat_service import OllamaChatFehler

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float | None = Field(default=None, ge=0, le=1)

    @field_validator("query")
    @classmethod
    def clean(cls, value):
        if not value.strip(): raise ValueError("Suchanfrage darf nicht leer sein.")
        return value.strip()


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value):
        value = value.strip()
        if len(value) < 3: raise ValueError("Frage muss mindestens 3 Zeichen enthalten.")
        return value


def service_call(call):
    try: return call()
    except (EmbeddingFehler, OllamaChatFehler, DokumentPfadFehler) as exc: raise HTTPException(503, str(exc)) from exc


@router.post("/index")
def index(): return service_call(lambda: KnowledgeService().index())

@router.post("/reindex")
def reindex(): return service_call(lambda: KnowledgeService().index(force=True))

@router.get("/statistics")
def statistics(): return KnowledgeService().statistics()

@router.post("/search")
def search(request: SearchRequest): return service_call(lambda: KnowledgeService().search(request.query, request.top_k, request.min_score))

@router.post("/ask")
def ask(request: AskRequest): return service_call(lambda: KnowledgeService().ask(request.question, request.top_k))

@router.get("/document/{document_id}")
def document(document_id: str):
    value = KnowledgeService().document(document_id)
    if value is None: raise HTTPException(404, "Dokument wurde nicht gefunden.")
    return value
