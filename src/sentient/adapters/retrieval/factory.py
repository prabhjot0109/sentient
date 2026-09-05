from __future__ import annotations

from pathlib import Path

from langchain_core.embeddings import Embeddings

from sentient.adapters.retrieval.base import VectorBackend
from sentient.adapters.retrieval.faiss_store import FaissBackend
from sentient.core.config import RAGSettings


def get_vector_backend(
    settings: RAGSettings, index_path: str | Path, embeddings: Embeddings
) -> VectorBackend:
    if settings.vector_backend == "qdrant":
        # Imported lazily so the FAISS default path never pays the qdrant-client /
        # fastembed import cost. index_path is unused by the Qdrant branch.
        from sentient.adapters.retrieval.qdrant_store import QdrantBackend

        return QdrantBackend(settings, embeddings)
    if settings.vector_backend == "pgvector":
        # Optional like Qdrant: a self-hosted deployment opts in with
        # `uv sync --group pgvector`; the FAISS default imports neither client.
        from sentient.adapters.retrieval.pgvector_store import PgVectorBackend

        return PgVectorBackend(settings, embeddings)
    return FaissBackend(settings, Path(index_path), embeddings)
