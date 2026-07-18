import os
from pathlib import Path


VERSION = "1.9.0"
PROJECT_PATH = Path(__file__).resolve().parent.parent
DROPBOX_PATH = Path(os.getenv("AKZENTA_DROPBOX_PATH", r"C:\Users\S. Vedder\Dropbox\AKZENTA AI"))
CHROMA_PATH = Path(os.getenv("AKZENTA_CHROMA_PATH", str(PROJECT_PATH / "data" / "chroma")))
CHROMA_COLLECTION = os.getenv("AKZENTA_CHROMA_COLLECTION", "akzenta_wissensbasis")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_EMBEDDING_URL = os.getenv("OLLAMA_EMBEDDING_URL", "http://localhost:11434/api/embed")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
OLLAMA_CHAT_URL = os.getenv("OLLAMA_CHAT_URL", "http://localhost:11434/api/chat")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3")
OLLAMA_REQUEST_TIMEOUT = int(os.getenv("OLLAMA_REQUEST_TIMEOUT", "180"))
CHAT_MAX_CONTEXT_CHARS = int(os.getenv("CHAT_MAX_CONTEXT_CHARS", "12000"))
CHAT_MAX_QUESTION_CHARS = int(os.getenv("CHAT_MAX_QUESTION_CHARS", "2000"))
CHAT_MIN_RELEVANCE = float(os.getenv("CHAT_MIN_RELEVANCE", "0.25"))
ALLOWED_ORIGINS = tuple(
    ursprung.strip()
    for ursprung in os.getenv(
        "AKZENTA_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if ursprung.strip()
)
RELEVANTE_ENDUNGEN = frozenset({".pdf", ".docx", ".xlsx", ".txt", ".pptx", ".ppsx"})
VORSCHAU_ZEICHEN = 3000
ABSCHNITT_ZEICHEN = int(os.getenv("AKZENTA_CHUNK_SIZE", "1000"))
ABSCHNITT_UEBERLAPPUNG = int(os.getenv("AKZENTA_CHUNK_OVERLAP", "150"))
RAG_DB_PATH = Path(os.getenv("AKZENTA_RAG_DB", str(PROJECT_PATH / "data" / "knowledge.sqlite3")))
RAG_CHUNK_SIZE = int(os.getenv("AKZENTA_RAG_CHUNK_SIZE", str(ABSCHNITT_ZEICHEN)))
RAG_CHUNK_OVERLAP = int(os.getenv("AKZENTA_RAG_CHUNK_OVERLAP", str(ABSCHNITT_UEBERLAPPUNG)))
RAG_MIN_SCORE = float(os.getenv("AKZENTA_RAG_MIN_SCORE", "0.25"))
RAG_TOP_K = int(os.getenv("AKZENTA_RAG_TOP_K", "5"))
AGENT_MOCK_MODE = os.getenv("AKZENTA_AGENT_MOCK_MODE", "true").lower() == "true"
AGENT_AUDIT_LOG = Path(os.getenv("AKZENTA_AGENT_AUDIT_LOG", str(PROJECT_PATH / "data" / "agent-audit.jsonl")))
ONOFFICE_ENABLED = os.getenv("ONOFFICE_ENABLED", "false").lower() == "true"
ONOFFICE_MODE = os.getenv("ONOFFICE_MODE", "mock").lower()
ONOFFICE_API_URL = os.getenv("ONOFFICE_API_URL", "https://api.onoffice.de/api/stable/api.php")
ONOFFICE_API_TOKEN = os.getenv("ONOFFICE_API_TOKEN", "")
ONOFFICE_API_SECRET = os.getenv("ONOFFICE_API_SECRET", "")
ONOFFICE_TIMEOUT_SECONDS = float(os.getenv("ONOFFICE_TIMEOUT_SECONDS", "15"))
ONOFFICE_FIELD_MAPPING_JSON = os.getenv("ONOFFICE_FIELD_MAPPING_JSON", "")
