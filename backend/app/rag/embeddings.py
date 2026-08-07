"""Pluggable sentence embedding.

Two backends, same model (`all-MiniLM-L6-v2`, 384-dim) so vectors are
interchangeable between them:

    fastembed             ONNX runtime. Clean aarch64 wheels, ~400 MB image.
                          This is what the Oracle ARM deployment uses.
    sentence-transformers PyTorch. ~2.5 GB and no usable aarch64 story, but
                          it is what most dev machines already have.

Selection is automatic - fastembed if importable, else sentence-transformers -
and can be pinned with EMBEDDING_BACKEND=fastembed|sentence-transformers.
"""

from __future__ import annotations

import os
from typing import Protocol

import numpy as np

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


class Embedder(Protocol):
    name: str

    def encode(self, texts: list[str]) -> np.ndarray:
        """Return float32 vectors, L2-normalised, shape (len(texts), EMBEDDING_DIM)."""
        ...


def _normalise(vectors: np.ndarray) -> np.ndarray:
    vectors = np.asarray(vectors, dtype="float32")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    # A zero vector would divide by zero; leave it as-is (it scores 0 against
    # everything, which is the right answer for an empty document).
    np.divide(vectors, norms, out=vectors, where=norms > 0)
    return vectors


class FastEmbedBackend:
    name = "fastembed"

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        from fastembed import TextEmbedding

        # The Docker build populates this cache so the container never reaches
        # HuggingFace at runtime - a first request that downloads 90 MB is the
        # difference between a 2-second and a 40-second first impression.
        cache_dir = os.getenv("FASTEMBED_CACHE_PATH") or None
        self._model = TextEmbedding(model_name=model_name, cache_dir=cache_dir)

    def encode(self, texts: list[str]) -> np.ndarray:
        return _normalise(np.array(list(self._model.embed(texts))))


class SentenceTransformerBackend:
    name = "sentence-transformers"

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> np.ndarray:
        return _normalise(self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False))


_BACKENDS = {
    "fastembed": FastEmbedBackend,
    "sentence-transformers": SentenceTransformerBackend,
}

# fastembed first: if both are installed, prefer the one the container ships.
_PREFERENCE = ("fastembed", "sentence-transformers")


def load_embedder(model_name: str = MODEL_NAME) -> Embedder:
    pinned = os.getenv("EMBEDDING_BACKEND", "").strip().lower()
    if pinned:
        if pinned not in _BACKENDS:
            raise ValueError(
                f"EMBEDDING_BACKEND={pinned!r} is not one of {sorted(_BACKENDS)}"
            )
        return _BACKENDS[pinned](model_name)

    errors = []
    for key in _PREFERENCE:
        try:
            return _BACKENDS[key](model_name)
        except ImportError as exc:
            errors.append(f"{key}: {exc}")

    raise ImportError(
        "No embedding backend available. Install one:\n"
        "  pip install fastembed              (recommended, ARM-friendly)\n"
        "  pip install sentence-transformers  (pulls PyTorch)\n"
        + "\n".join(f"  tried {e}" for e in errors)
    )
