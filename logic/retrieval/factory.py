from __future__ import annotations

from pathlib import Path

from logic.config import RAGSettings
from logic.retrieval.base import VectorBackend
from logic.retrieval.faiss_store import FaissBackend


def get_vector_backend(settings: RAGSettings, index_path, embeddings) -> VectorBackend:
    if settings.vector_backend == "qdrant":
        raise NotImplementedError(
            "Qdrant backend arrives in Plan 02. Set VECTOR_BACKEND=faiss for now."
        )
    return FaissBackend(settings, Path(index_path), embeddings)
