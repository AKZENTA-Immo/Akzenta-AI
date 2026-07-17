import requests

from backend import config


class EmbeddingFehler(RuntimeError):
    pass


class OllamaEmbeddingService:
    def __init__(self, url: str | None = None, modell: str | None = None):
        self.url = url or config.OLLAMA_EMBEDDING_URL
        self.modell = modell or config.OLLAMA_EMBEDDING_MODEL

    def embed(self, texte: list[str]) -> list[list[float]]:
        if not texte:
            return []
        try:
            antwort = requests.post(
                self.url,
                json={"model": self.modell, "input": texte},
                timeout=120,
            )
            antwort.raise_for_status()
            antwort.encoding = "utf-8"
            daten = antwort.json()
        except requests.ConnectionError as exc:
            raise EmbeddingFehler("Ollama ist für Embeddings nicht erreichbar.") from exc
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                meldung = f"Embedding-Modell '{self.modell}' ist in Ollama nicht verfügbar."
            else:
                meldung = "Ollama konnte keine Embeddings erzeugen."
            raise EmbeddingFehler(meldung) from exc
        except (requests.RequestException, ValueError) as exc:
            raise EmbeddingFehler("Ollama lieferte keine gültige Embedding-Antwort.") from exc
        embeddings = daten.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texte):
            raise EmbeddingFehler("Ollama lieferte eine unvollständige Embedding-Antwort.")
        return embeddings
