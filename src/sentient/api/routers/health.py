"""Liveness and runtime-configuration report.

Per spec D6 no service is created for a passthrough: this reads the default
archive and the resolved settings directly.
"""

from __future__ import annotations

from fastapi import APIRouter

from sentient.api import deps
from sentient.core.config import load_rag_settings

router = APIRouter()


@router.get("/health")
def health_check():
    archives = deps.get_default_archives()
    settings = load_rag_settings()
    index_metadata = archives.get_index_metadata()

    return {
        "status": "online",
        "brain_loaded": deps.object_registry.size() > 0,
        "index_loaded": archives.index_exists(),
        "source_count": len(archives.list_sources()),
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "search_type": settings.search_type,
        "top_k": settings.top_k,
        "persona": index_metadata.get("persona") if index_metadata else None,
        "index_metadata": index_metadata,
    }
