import os
from pathlib import Path


VERSION = "0.4.1"
DROPBOX_PATH = Path(os.getenv("AKZENTA_DROPBOX_PATH", r"C:\Users\S. Vedder\Dropbox\AKZENTA AI"))
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
RELEVANTE_ENDUNGEN = frozenset({".pdf", ".docx", ".xlsx", ".txt", ".pptx", ".ppsx"})
VORSCHAU_ZEICHEN = 3000
