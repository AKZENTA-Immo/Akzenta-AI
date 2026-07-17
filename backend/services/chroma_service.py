import json
from datetime import datetime, timezone
from pathlib import Path

from backend import config


class ChromaFehler(RuntimeError):
    pass


class ChromaService:
    def __init__(self, pfad: Path | None = None, collection_name: str | None = None):
        self.pfad = (pfad or config.CHROMA_PATH).resolve()
        self.collection_name = collection_name or config.CHROMA_COLLECTION
        self._collection = None

    @property
    def state_path(self) -> Path:
        return self.pfad / "index_state.json"

    def collection(self):
        if self._collection is None:
            try:
                import chromadb

                self.pfad.mkdir(parents=True, exist_ok=True)
                client = chromadb.PersistentClient(path=str(self.pfad))
                self._collection = client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as exc:
                raise ChromaFehler("Die lokale ChromaDB ist nicht verfügbar oder nicht beschreibbar.") from exc
        return self._collection

    def lade_status(self) -> dict:
        if not self.state_path.exists():
            return {"dokumente": {}, "letzte_indexierung": None}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ChromaFehler("Der lokale Indexzustand konnte nicht gelesen werden.") from exc

    def speichere_status(self, dokumente: dict) -> str:
        zeitpunkt = datetime.now(timezone.utc).isoformat()
        daten = {"dokumente": dokumente, "letzte_indexierung": zeitpunkt}
        try:
            self.pfad.mkdir(parents=True, exist_ok=True)
            temporaer = self.state_path.with_suffix(".tmp")
            temporaer.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")
            temporaer.replace(self.state_path)
        except OSError as exc:
            raise ChromaFehler("Der lokale Indexzustand konnte nicht gespeichert werden.") from exc
        return zeitpunkt

    def upsert(self, ids: list[str], texte: list[str], metadaten: list[dict], embeddings: list[list[float]]):
        try:
            self.collection().upsert(ids=ids, documents=texte, metadatas=metadaten, embeddings=embeddings)
        except Exception as exc:
            raise ChromaFehler("Abschnitte konnten nicht in ChromaDB gespeichert werden.") from exc

    def entferne_dokument(self, dokument_id: str):
        try:
            self.collection().delete(where={"dokument_id": dokument_id})
        except Exception as exc:
            raise ChromaFehler("Alte Dokumentabschnitte konnten nicht entfernt werden.") from exc

    def leere_collection(self) -> None:
        try:
            collection = self.collection()
            ids = collection.get(include=[]).get("ids", [])
            for start in range(0, len(ids), 1000):
                collection.delete(ids=ids[start:start + 1000])
        except Exception as exc:
            raise ChromaFehler("Die lokale Wissensbasis konnte nicht für den Neuaufbau geleert werden.") from exc

    def suche(self, embedding: list[float], limit: int) -> list[dict]:
        try:
            ergebnis = self.collection().query(
                query_embeddings=[embedding], n_results=limit, include=["documents", "metadatas", "distances"]
            )
        except Exception as exc:
            raise ChromaFehler("Die lokale Wissensbasis konnte nicht durchsucht werden.") from exc
        treffer = []
        for text, metadata, distanz in zip(
            ergebnis.get("documents", [[]])[0], ergebnis.get("metadatas", [[]])[0], ergebnis.get("distances", [[]])[0]
        ):
            treffer.append({"text": text, "metadata": metadata, "relevanz": round(max(0.0, min(1.0, 1.0 - distanz)), 6)})
        return treffer

    def anzahl_abschnitte(self) -> int:
        return self.collection().count()

    def relativer_speicherort(self) -> str:
        try:
            return self.pfad.relative_to(config.PROJECT_PATH.resolve()).as_posix()
        except ValueError:
            return "data/chroma"
