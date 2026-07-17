import requests
from fastapi import FastAPI, HTTPException

from backend import config
from backend.routers.dokumente import router as dokumente_router
from backend.routers.wissensbasis import router as wissensbasis_router


app = FastAPI(title="AKZENTA AI", version=config.VERSION)
app.include_router(dokumente_router)
app.include_router(wissensbasis_router)


@app.get("/")
def start():
    return {"status": "AKZENTA AI läuft", "branche": "Immobilienmakler", "version": config.VERSION}


@app.get("/immobilien-text")
def immobilien_text():
    prompt = """
    Du bist ein professioneller Assistent für ein Immobilienmaklerunternehmen in Hamburg.
    Schreibe einen kurzen, seriösen deutschen Exposétext für eine moderne Eigentumswohnung.
    Antworte ausschließlich auf Deutsch.
    """
    try:
        response = requests.post(
            config.OLLAMA_URL,
            json={"model": config.OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        antwort = response.json().get("response")
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail=f"Ollama ist nicht erreichbar: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Ollama lieferte kein gültiges JSON.") from exc
    if not antwort:
        raise HTTPException(status_code=502, detail="Ollama lieferte keinen Immobilientext.")
    return {"antwort": antwort}
