from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from langchain_core.documents import Document


@runtime_checkable
class VectorBackend(Protocol):
    """Async storage/retrieval seam so FAISS and Qdrant are interchangeable.

    I/O methods are coroutines: Qdrant awaits real network calls; FAISS offloads
    its synchronous CPU work with asyncio.to_thread so it never blocks the loop.
    `retrieve` returns (Document, score) tuples (score None when unavailable).
    `user_key` filters to one tenant's docs (Qdrant payload filter); single-tenant
    backends ignore it.

    Project partitioning (v2): `project_id` scopes writes/reads to one project and
    `embedding_signature` records which embedding model produced the vectors, so a
    reindex can detect a signature change. FAISS ignores both (single-project,
    single-signature); Qdrant filters/stamps them in each point's payload.
    `clear_project` drops one project's vectors (Qdrant); FAISS is a no-op.
    """

    async def index(
        self,
        chunks: list[Document],
        *,
        source_names: list[str] | None = None,
        persona: str = "",
        user_key: str | None = None,
        project_id: str | None = None,
        embedding_signature: str | None = None,
    ) -> dict[str, Any] | None: ...
    async def add(
        self,
        chunks: list[Document],
        *,
        source_names: list[str] | None = None,
        persona: str = "",
        user_key: str | None = None,
        project_id: str | None = None,
        embedding_signature: str | None = None,
    ) -> dict[str, Any] | None: ...
    async def remove(self, source: str) -> dict[str, Any] | None: ...
    async def retrieve(
        self, query: str, *, k: int | None = None, search_type: str | None = None,
        min_score: float | None = None, user_key: str | None = None,
        project_id: str | None = None, embedding_signature: str | None = None,
    ) -> list[tuple[Document, float | None]]: ...
    def clear_project(self, user_key: str | None, project_id: str) -> None: ...
    def exists(self) -> bool: ...
    def metadata(self) -> dict[str, Any] | None: ...
    def invalidate_cache(self) -> None: ...
    def reset(self) -> None: ...
