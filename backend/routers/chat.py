from fastapi import APIRouter, HTTPException

from backend import config
from backend.models.chat_models import DokumentChatAnfrage, DokumentChatAntwort
from backend.services.chat_service import DokumentChatService, WissensbasisLeer
from backend.services.chroma_service import ChromaFehler, ChromaService
from backend.services.embedding_service import EmbeddingFehler
from backend.services.ollama_chat_service import (
    ChatModellFehlt,
    OllamaChatFehler,
    OllamaChatService,
    OllamaNichtErreichbar,
    OllamaTimeout,
    UngueltigeModellAntwort,
)


router = APIRouter(prefix="/chat", tags=["Dokumentenchat"])


@router.post("/dokumente", response_model=DokumentChatAntwort)
def dokumentenchat(anfrage: DokumentChatAnfrage) -> DokumentChatAntwort:
    try:
        return DokumentChatService().beantworte(anfrage.frage, anfrage.limit)
    except WissensbasisLeer as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OllamaTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except (OllamaNichtErreichbar, ChatModellFehlt, EmbeddingFehler, ChromaFehler) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (UngueltigeModellAntwort, OllamaChatFehler) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Der Dokumentenchat konnte nicht verarbeitet werden.") from exc


@router.get("/status")
def chat_status() -> dict[str, object]:
    chat = OllamaChatService()
    ollama_erreichbar, chat_modell_verfuegbar, modelle = chat.modellstatus()
    embedding_verfuegbar = any(
        name == config.OLLAMA_EMBEDDING_MODEL or name.split(":", 1)[0] == config.OLLAMA_EMBEDDING_MODEL
        for name in modelle
    )
    chromadb_erreichbar = True
    indexierte_dokumente = 0
    gespeicherte_abschnitte = 0
    fehler = []
    try:
        chroma = ChromaService()
        indexierte_dokumente = len(chroma.lade_status().get("dokumente", {}))
        gespeicherte_abschnitte = chroma.anzahl_abschnitte()
    except ChromaFehler as exc:
        chromadb_erreichbar = False
        fehler.append(str(exc))
    if not ollama_erreichbar:
        fehler.append("Ollama ist nicht erreichbar.")
    elif not chat_modell_verfuegbar:
        fehler.append(f"Chat-Modell '{config.OLLAMA_CHAT_MODEL}' ist nicht installiert.")
    if ollama_erreichbar and not embedding_verfuegbar:
        fehler.append(f"Embedding-Modell '{config.OLLAMA_EMBEDDING_MODEL}' ist nicht installiert.")
    if gespeicherte_abschnitte == 0:
        fehler.append("Die Wissensbasis enthält keine indexierten Abschnitte.")
    bereit = ollama_erreichbar and chat_modell_verfuegbar and embedding_verfuegbar and chromadb_erreichbar and gespeicherte_abschnitte > 0
    return {
        "ollama_erreichbar": ollama_erreichbar,
        "chat_modell_verfuegbar": chat_modell_verfuegbar,
        "chat_modell": config.OLLAMA_CHAT_MODEL,
        "embedding_modell": config.OLLAMA_EMBEDDING_MODEL,
        "chromadb_erreichbar": chromadb_erreichbar,
        "indexierte_dokumente": indexierte_dokumente,
        "gespeicherte_abschnitte": gespeicherte_abschnitte,
        "chat_bereit": bereit,
        "fehlermeldung": " ".join(fehler) if fehler else None,
    }
