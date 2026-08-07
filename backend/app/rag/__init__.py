"""Hybrid retrieval: FAISS vector search plus a deterministic rule engine."""

from .embeddings import EMBEDDING_DIM, MODEL_NAME, load_embedder
from .retriever import IncidentRetriever, get_retriever, search_incidents
from .rules import check_compatibility_rules

__all__ = [
    "EMBEDDING_DIM",
    "MODEL_NAME",
    "IncidentRetriever",
    "check_compatibility_rules",
    "get_retriever",
    "load_embedder",
    "search_incidents",
]
