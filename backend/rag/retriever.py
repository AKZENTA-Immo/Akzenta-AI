from backend import config


class Retriever:
    def __init__(self, store, embeddings): self.store, self.embeddings = store, embeddings

    def search(self, query: str, top_k: int | None = None, min_score: float | None = None):
        limit = top_k or config.RAG_TOP_K
        threshold = config.RAG_MIN_SCORE if min_score is None else min_score
        return [r for r in self.store.search(self.embeddings.embed_one(query), limit) if r["score"] >= threshold]
