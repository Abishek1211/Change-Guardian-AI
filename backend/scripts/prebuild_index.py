"""Bake the embedding model and corpus vectors into the image at build time.

Run during `docker build`. Two things happen:

  1. The ONNX model is downloaded into FASTEMBED_CACHE_PATH, so the running
     container never reaches HuggingFace. A cold first request that has to pull
     90 MB is the difference between a 2-second and a 40-second first
     impression - and on a box with no GPU, the one thing this demo has going
     for it is that it feels instant.
  2. The incident corpus is embedded once and written to a .npz next to the
     data, fingerprinted by corpus text + model name so a stale cache is
     ignored rather than silently served.

    python backend/scripts/prebuild_index.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from app.data import incident_docs  # noqa: E402
from app.rag.embeddings import MODEL_NAME, load_embedder  # noqa: E402
from app.rag.retriever import VECTOR_CACHE, _corpus_text, corpus_fingerprint  # noqa: E402


def main() -> int:
    started = time.monotonic()

    embedder = load_embedder()
    print(f"backend  : {embedder.name}")
    print(f"model    : {MODEL_NAME}")

    vectors = embedder.encode([_corpus_text(doc) for doc in incident_docs])
    print(f"embedded : {vectors.shape[0]} documents, dim={vectors.shape[1]}")

    VECTOR_CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        VECTOR_CACHE,
        vectors=vectors,
        fingerprint=corpus_fingerprint(incident_docs),
    )

    size_kb = VECTOR_CACHE.stat().st_size / 1024
    print(f"wrote    : {VECTOR_CACHE.name} ({size_kb:.1f} KB)")

    # Prove the cache round-trips, reusing the loaded model rather than
    # constructing a second one - loading the ONNX session twice doubles build
    # time for no benefit.
    with np.load(VECTOR_CACHE) as cached:
        if str(cached["fingerprint"]) != corpus_fingerprint(incident_docs):
            print("FAILED: fingerprint does not round-trip")
            return 1
        restored = cached["vectors"].astype("float32")

    if not np.allclose(restored, vectors, atol=1e-6):
        print("FAILED: cached vectors do not match what was embedded")
        return 1

    query = embedder.encode(["Spring Boot upgrade Java version"])[0]
    ranked = np.argsort(-(restored @ query))[:3]
    hits = [(incident_docs[i]["id"], round(float(restored[i] @ query), 3)) for i in ranked]
    print(f"sanity   : {hits}")

    if hits[0][1] <= 0:
        print("FAILED: retrieval returned nothing useful")
        return 1

    # INC-002 is the Spring Boot migration incident - if the nearest neighbour
    # for this query is anything else, the corpus or model changed meaningfully.
    if hits[0][0] != "INC-002":
        print(f"WARNING: expected INC-002 as top hit, got {hits[0][0]}")

    print(f"\ndone in {time.monotonic() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
