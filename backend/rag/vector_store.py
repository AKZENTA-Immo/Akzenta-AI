import json
import math
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from backend import config


SCHEMA_VERSION = 1


class VectorStore:
    def __init__(self, database_path: Path | str | None = None):
        self.database_path = Path(database_path or config.RAG_DB_PATH)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def connect(self):
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def transaction(self):
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback(); raise
        finally: connection.close()

    def migrate(self):
        with self.transaction() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS rag_schema_version (version INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, filename TEXT NOT NULL, path TEXT NOT NULL UNIQUE, folder TEXT NOT NULL,
                    document_type TEXT NOT NULL, modified_at REAL NOT NULL, fingerprint TEXT NOT NULL,
                    indexed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL, text TEXT NOT NULL, page INTEGER, section TEXT,
                    filename TEXT NOT NULL, path TEXT NOT NULL, folder TEXT NOT NULL,
                    document_type TEXT NOT NULL, modified_at REAL NOT NULL,
                    UNIQUE(document_id, position)
                );
                CREATE TABLE IF NOT EXISTS embeddings (
                    chunk_id TEXT PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
                    model TEXT NOT NULL, dimensions INTEGER NOT NULL, vector TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id, position);
                CREATE INDEX IF NOT EXISTS idx_documents_path ON documents(path);
            """)
            row = db.execute("SELECT version FROM rag_schema_version LIMIT 1").fetchone()
            if row is None: db.execute("INSERT INTO rag_schema_version(version) VALUES (?)", (SCHEMA_VERSION,))
            elif row[0] > SCHEMA_VERSION: raise RuntimeError("Unbekannte neuere RAG-Schema-Version.")

    def document_fingerprints(self):
        with self.connect() as db:
            return {r["id"]: r["fingerprint"] for r in db.execute("SELECT id,fingerprint FROM documents")}

    def replace_document(self, document, fingerprint, chunks, vectors, model):
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction() as db:
            db.execute("DELETE FROM documents WHERE id=?", (document.id,))
            db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)", (document.id, document.filename, document.path,
                document.folder, document.document_type, document.modified_at, fingerprint, now))
            for chunk, vector in zip(chunks, vectors):
                chunk_id = f"{document.id}:{chunk.position}"
                db.execute("INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?,?,?,?)", (chunk_id, document.id, chunk.position,
                    chunk.text, chunk.page, chunk.section, document.filename, document.path, document.folder,
                    document.document_type, document.modified_at))
                db.execute("INSERT INTO embeddings VALUES(?,?,?,?)", (chunk_id, model, len(vector), json.dumps(vector)))

    def remove_missing(self, ids):
        with self.transaction() as db:
            rows = db.execute("SELECT id FROM documents").fetchall()
            missing = [r[0] for r in rows if r[0] not in ids]
            db.executemany("DELETE FROM documents WHERE id=?", [(i,) for i in missing])
            return len(missing)

    def clear(self):
        with self.transaction() as db: db.execute("DELETE FROM documents")

    @staticmethod
    def cosine(a, b):
        if len(a) != len(b): return 0.0
        denom = math.sqrt(sum(x*x for x in a)) * math.sqrt(sum(x*x for x in b))
        return sum(x*y for x, y in zip(a, b)) / denom if denom else 0.0

    def search(self, vector, limit):
        with self.connect() as db:
            rows = db.execute("SELECT c.*,e.vector FROM chunks c JOIN embeddings e ON e.chunk_id=c.id").fetchall()
        results = [{**dict(r), "score": round(max(0.0, self.cosine(vector, json.loads(r["vector"]))), 6)} for r in rows]
        for result in results: result.pop("vector", None)
        return sorted(results, key=lambda r: r["score"], reverse=True)[:limit]

    def statistics(self):
        with self.connect() as db:
            documents = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            chunks = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            embeddings = db.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
            last = db.execute("SELECT MAX(indexed_at) FROM documents").fetchone()[0]
        return {"documents": documents, "chunks": chunks, "embeddings": embeddings, "last_indexed_at": last}

    def document(self, document_id, limit=100):
        with self.connect() as db:
            document = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
            if not document: return None
            chunks = db.execute("SELECT position,text,page,section FROM chunks WHERE document_id=? ORDER BY position LIMIT ?", (document_id, limit)).fetchall()
        return {**dict(document), "chunks": [dict(r) for r in chunks], "preview": "\n\n".join(r["text"] for r in chunks)[:10000]}
