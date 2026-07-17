import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend import config
from backend.routers.dokument_ordner import router as dokument_ordner_router
from backend.routers.dokumente import router as dokumente_router
from backend.routers.wissensbasis import router as wissensbasis_router
from backend.routers.chat import router as chat_router
from backend.responses import UTF8JSONResponse


