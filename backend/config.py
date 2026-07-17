import os
from pathlib import Path


VERSION = "0.5"
PROJECT_PATH = Path(__file__).resolve().parent.parent
DROPBOX_PATH = Path(os.getenv("AKZENTA_DROPBOX_PATH", r"C:\Users\S. Vedder\Dropbox\AKZENTA AI"))
CHROMA_PATH = Path(os.getenv("AKZENTA_CHROMA_PATH", str(PROJECT_PATH / "data" / "chroma")))
CHROMA_COLLECTION = os.getenv("AKZENTA_CHROMA_COLLECTION", "akzenta_wissensbasis")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_EMBEDDING_URL = os.getenv("OLLAMA_EMBEDDING_URL", "http://localhost:11434/api/embed")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
RELEVANTE_ENDUNGEN = frozenset({".pdf", ".docx", ".xlsx", ".txt", ".pptx", ".ppsx"})
VORSCHAU_ZEICHEN = 3000
ABSCHNITT_ZEICHEN = int(os.getenv("AKZENTA_CHUNK_SIZE", "1000"))
ABSCHNITT_UEBERLAPPUNG = int(os.getenv("AKZENTA_CHUNK_OVERLAP", "150"))
