from __future__ import annotations

from pathlib import Path

from sentient.core.config import RAGSettings
from logic.retrieval.base import VectorBackend
from logic.retrieval.faiss_store import FaissBackend


def get_vector_backend(settings: RAGSettings, index_path, embeddings) -> VectorBackend:
    if settings.vector_backend == "qdrant":
        # Imported lazily so the FAISS default path never pays the qdrant-client /
        # fastembed import cost. index_path is unused by the Qdrant branch.
        from logic.retrieval.qdrant_store import QdrantBackend

        return QdrantBackend(settings, embeddings)
    return FaissBackend(settings, Path(index_path), embeddings)
