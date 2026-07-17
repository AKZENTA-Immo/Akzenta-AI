from fastapi import APIRouter, HTTPException, Query

from backend import config
from backend.services.chroma_service import ChromaFehler, ChromaService
from backend.services.embedding_service import EmbeddingFehler, OllamaEmbeddingService
from backend.services.index_service import IndexService
from backend.services.dokument_scanner import DokumentPfadFehler


router = APIRouter(prefix="/wissensbasis", tags=["Wissensbasis"])


def _formatiere_treffer(treffer: dict) -> dict:
    metadata = treffer["metadata"]
    ausgabe = {
        "dokument_id": metadata["dokument_id"],
        "dateiname": metadata["dateiname"],
        "pfad": metadata["pfad"],
        "textausschnitt": treffer["text"],
        "relevanzwert": treffer["relevanz"],
        "abschnittsnummer": metadata["abschnittsnummer"],
    }
    for feld in ("seite", "folie", "tabellenblatt"):
        if feld in metadata:
            ausgabe[feld] = metadata[feld]
    return ausgabe


@router.post("/indexieren")
def indexieren():
    try:
        return IndexService().indexiere()
    except (ChromaFehler, EmbeddingFehler, DokumentPfadFehler) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/status")
def status():
    chroma = ChromaService()
    try:
        zustand = chroma.lade_status()
        return {
            "chromadb_erreichbar": True,
            "collection_name": chroma.collection_name,
            "indexierte_dokumente": len(zustand.get("dokumente", {})),
            "gespeicherte_abschnitte": chroma.anzahl_abschnitte(),
            "embedding_modell": config.OLLAMA_EMBEDDING_MODEL,
            "speicherort": chroma.relativer_speicherort(),
            "letzte_indexierung": zustand.get("letzte_indexierung"),
        }
    except ChromaFehler as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/suche")
def suche(q: str = Query(min_length=1), limit: int = Query(default=5, ge=1, le=20)):
    suchtext = q.strip()
    if not suchtext:
        raise HTTPException(status_code=422, detail="Die Suchanfrage darf nicht leer sein.")
    try:
        embedding_service = OllamaEmbeddingService()
        treffer = ChromaService().suche(embedding_service.embed([suchtext])[0], limit)
    except (ChromaFehler, EmbeddingFehler) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "status": "ok",
        "anfrage": suchtext,
        "anzahl": len(treffer),
        "treffer": [_formatiere_treffer(t) for t in treffer],
    }
