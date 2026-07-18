import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend import config
from backend.routers.dokument_ordner import router as dokument_ordner_router
from backend.routers.dokumente import router as dokumente_router
from backend.routers.wissensbasis import router as wissensbasis_router
from backend.routers.chat import router as chat_router
from backend.routers.agents import router as agents_router
from backend.routers.agent_manager import router as agent_manager_router
from backend.routers.onoffice import router as onoffice_router
from backend.routers.knowledge import router as knowledge_router
from backend.routers.phone import router as phone_router
from backend.routers.dashboard import router as dashboard_router
from backend.responses import UTF8JSONResponse


app = FastAPI(title="AKZENTA AI", version=config.VERSION, default_response_class=UTF8JSONResponse)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(config.ALLOWED_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)
app.include_router(dokumente_router)
app.include_router(dokument_ordner_router)
app.include_router(wissensbasis_router)
app.include_router(chat_router)
app.include_router(agents_router)
app.include_router(agent_manager_router)
app.include_router(onoffice_router)
app.include_router(knowledge_router)
app.include_router(phone_router)
app.include_router(dashboard_router)


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
