from backend.services.embedding_service import EmbeddingFehler, OllamaEmbeddingService


class LocalEmbeddingService(OllamaEmbeddingService):
    """Ollama-only embedding adapter; intentionally has no cloud fallback."""

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


__all__ = ["EmbeddingFehler", "LocalEmbeddingService"]
