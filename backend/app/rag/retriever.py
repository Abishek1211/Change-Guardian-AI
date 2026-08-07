"""Vector search over the incident corpus (agent 4, semantic half).

Built lazily on first use, not at import. Under uvicorn the module graph is
imported before the server binds its port, so building the index at import time
would delay startup and run once per worker.

FAISS is used when present, with a numpy fallback. At six incident documents
the two are indistinguishable - an exhaustive numpy dot product over a (6, 384)
matrix is already optimal, and IndexFlatIP does exactly that internally.
"""

from __future__ import annotations

import threading
from typing import Any

import numpy as np

from ..data import incident_docs
from .embeddings import Embedder, load_embedder


def _corpus_text(doc: dict[str, Any]) -> str:
    return f"{doc['title']}. {doc['root_cause']} Lesson: {doc['lesson']}"


class IncidentRetriever:
    def __init__(self, docs: list[dict[str, Any]] | None = None) -> None:
        self._docs = docs if docs is not None else incident_docs
        self._lock = threading.Lock()
        self._embedder: Embedder | None = None
        self._vectors: np.ndarray | None = None
        self._index: Any = None
        self._backend = "uninitialised"

    # ------------------------------------------------------------------ build

    def _ensure_ready(self) -> None:
        if self._vectors is not None:
            return
        with self._lock:
            if self._vectors is not None:  # another thread won the race
                return

            embedder = load_embedder()
            vectors = embedder.encode([_corpus_text(d) for d in self._docs])

            index = None
            backend = f"numpy ({embedder.name})"
            try:
                import faiss

                index = faiss.IndexFlatIP(vectors.shape[1])
                index.add(vectors)
                backend = f"faiss ({embedder.name})"
            except ImportError:
                pass

            self._embedder = embedder
            self._index = index
            self._vectors = vectors
            self._backend = backend

    # ----------------------------------------------------------------- search

    def search(self, query: str, k: int = 3) -> list[dict[str, Any]]:
        self._ensure_ready()
        assert self._embedder is not None and self._vectors is not None

        k = max(1, min(k, len(self._docs)))
        query_vec = self._embedder.encode([query])

        if self._index is not None:
            scores, indices = self._index.search(query_vec, k)
            pairs = zip(scores[0], indices[0])
        else:
            # Vectors are L2-normalised, so a dot product is cosine similarity.
            sims = (self._vectors @ query_vec[0]).astype("float32")
            top = np.argsort(-sims)[:k]
            pairs = ((sims[i], i) for i in top)

        results = []
        for score, idx in pairs:
            if idx < 0:  # FAISS pads with -1 when it has fewer vectors than k
                continue
            doc = dict(self._docs[int(idx)])
            doc["sim"] = round(float(score), 3)
            results.append(doc)
        return results

    @property
    def backend(self) -> str:
        return self._backend

    def warmup(self) -> str:
        """Build the index ahead of the first request. Called on app startup so
        the first visitor does not pay the model load."""
        self._ensure_ready()
        return self._backend


_retriever = IncidentRetriever()


def search_incidents(query: str, k: int = 3) -> list[dict[str, Any]]:
    return _retriever.search(query, k)


def get_retriever() -> IncidentRetriever:
    return _retriever
