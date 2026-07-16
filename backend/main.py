import os
from collections import Counter
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException


app = FastAPI(title="AKZENTA AI", version="0.3")

DROPBOX_PATH = Path(
    os.getenv("AKZENTA_DROPBOX_PATH", r"C:\Users\S. Vedder\Dropbox\AKZENTA AI")
)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
RELEVANTE_ENDUNGEN = frozenset({".pdf", ".docx", ".xlsx", ".txt", ".pptx", ".ppsx"})


def _relevante_dokumente() -> list[Path]:
    """Liefert relevante Dateien aus der Wissensbasis, ohne sie zu verändern."""
    if not DROPBOX_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Dropbox-Ordner nicht gefunden: {DROPBOX_PATH}",
        )
    if not DROPBOX_PATH.is_dir():
        raise HTTPException(
            status_code=503,
            detail=f"Der konfigurierte Dropbox-Pfad ist kein Ordner: {DROPBOX_PATH}",
        )

    try:
        return sorted(
            (
                datei
                for datei in DROPBOX_PATH.rglob("*")
                if datei.is_file() and datei.suffix.lower() in RELEVANTE_ENDUNGEN
            ),
            key=lambda datei: str(datei).lower(),
        )
    except (OSError, PermissionError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Dropbox-Wissensbasis konnte nicht gelesen werden: {exc}",
        ) from exc


def _hauptordner(datei: Path) -> str:
    relativ = datei.relative_to(DROPBOX_PATH)
    return relativ.parts[0] if len(relativ.parts) > 1 else "Stammordner"


@app.get("/")
def start():
    return {
        "status": "AKZENTA AI läuft",
        "branche": "Immobilienmakler",
        "version": "0.3",
    }


@app.get("/immobilien-text")
def immobilien_text():
    prompt = """
    Du bist ein professioneller Assistent für ein Immobilienmaklerunternehmen in Hamburg.
    Schreibe einen kurzen, seriösen deutschen Exposétext für eine moderne Eigentumswohnung.
    Antworte ausschließlich auf Deutsch.
    """

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        antwort = response.json().get("response")
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama ist nicht erreichbar oder meldet einen Fehler: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Ollama hat keine gültige JSON-Antwort geliefert.",
        ) from exc

    if not antwort:
        raise HTTPException(
            status_code=502,
            detail="Ollama hat keinen Immobilientext geliefert.",
        )
    return {"antwort": antwort}


@app.get("/dokumente")
def dokumente():
    dateien = _relevante_dokumente()
    return {
        "status": "ok",
        "anzahl": len(dateien),
        "dateien": [
            {
                "name": datei.name,
                "pfad": str(datei),
                "endung": datei.suffix.lower(),
                "ordner": str(datei.parent),
            }
            for datei in dateien
        ],
    }


@app.get("/dokumente/statistik")
def dokumente_statistik():
    dateien = _relevante_dokumente()
    nach_endung = Counter(datei.suffix.lower() for datei in dateien)
    nach_hauptordner = Counter(_hauptordner(datei) for datei in dateien)

    return {
        "status": "ok",
        "gesamtzahl": len(dateien),
        "nach_endung": dict(sorted(nach_endung.items())),
        "nach_hauptordner": dict(sorted(nach_hauptordner.items())),
    }
