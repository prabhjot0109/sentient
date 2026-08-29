from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient, models

from sentient.core.config import RAGSettings
from sentient.core.logging import get_logger

log = get_logger(__name__)

DENSE = "dense"
SPARSE = "sparse"

# Payload field paths. langchain-qdrant nests a document's metadata under a
# "metadata" key in the point payload, so every tenant/project filter targets
# "metadata.<field>" (verified against langchain-qdrant 0.2.1).
_USER_KEY = "metadata.user_key"
_PROJECT_ID = "metadata.project_id"
_SIGNATURE = "metadata.embedding_signature"
_SOURCE = "metadata.source"

# EVERY field this backend ever puts in a Filter needs a keyword payload index.
# Not for speed. A Qdrant Cloud cluster runs strict mode with
# `unindexed_filtering_retrieve` disabled, so filtering on an unindexed field is
# refused outright with INVALID_ARGUMENT "Index required but not found" -- which
# `services/chat._retrieve` catches and downgrades to an ungrounded answer. The
# result is a project whose lore is indexed, whose upload succeeded, and whose
# NPC quietly ignores all of it. Measured 2026-08-29 against Qdrant Cloud with
# only user_key and project_id indexed.
_INDEXED_FIELDS = (_USER_KEY, _PROJECT_ID, _SIGNATURE, _SOURCE)

# One asyncio.Lock per event loop guards the one-time collection setup so
# concurrent first writes don't both try to create the collection. asyncio.Lock
# binds to a loop, so key by loop id (same pattern as faiss_store).
_setup_locks: dict[int, asyncio.Lock] = {}


def _get_setup_lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    lock = _setup_locks.get(id(loop))
    if lock is None:
        lock = asyncio.Lock()
        _setup_locks[id(loop)] = lock
    return lock


class QdrantBackend:
    """Async Qdrant hybrid impl of VectorBackend.

    Dense vectors come from the provider embeddings (Google/OpenAI/HF); sparse
    vectors from local FastEmbed BM25. RetrievalMode.HYBRID runs both server-side
    and fuses them with RRF -- no Python-side merge, no cross-encoder. A shared
    collection is partitioned by `user_key` (tenant) and `project_id`, and stamped
    with `embedding_signature`, all enforced as a server-side payload Filter so
    cross-tenant, cross-project and stale-dimension vectors are never returned.

    langchain-qdrant 0.2.1 drives everything through one *sync* QdrantClient (its
    async methods are thin executor wrappers), so, exactly like FaissBackend, this
    backend keeps the client sync and offloads each blocking call with
    asyncio.to_thread -- the event loop never blocks.
    """

    def __init__(
        self, settings: RAGSettings, embeddings: Embeddings, *, location: str | None = None
    ) -> None:
        self.settings = settings
        self.embeddings = embeddings
        self.collection = settings.qdrant_collection
        self.sparse = FastEmbedSparse(model_name=settings.sparse_model)
        self._location = location  # ":memory:" in tests; None in prod (use url)
        self._client: QdrantClient | None = None
        self._store: QdrantVectorStore | None = None
        self._ready = False

    # ---- client / collection construction ----
    def _client_kwargs(self) -> dict[str, Any]:
        if self._location:
            return {"location": self._location}
        return {
            "url": self.settings.qdrant_url,
            "api_key": self.settings.qdrant_api_key,
            "prefer_grpc": self.settings.qdrant_prefer_grpc,
        }

    def _sync_client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(**self._client_kwargs())
        return self._client

    def _ensure_collection_sync(self) -> None:
        client = self._sync_client()
        if not client.collection_exists(self.collection):
            dim = len(self.embeddings.embed_query("dimension probe"))
            client.create_collection(
                collection_name=self.collection,
                vectors_config={
                    DENSE: models.VectorParams(size=dim, distance=models.Distance.COSINE)
                },
                sparse_vectors_config={SPARSE: models.SparseVectorParams()},
                hnsw_config=models.HnswConfigDiff(m=16, ef_construct=100),
                quantization_config=models.ScalarQuantization(
                    scalar=models.ScalarQuantizationConfig(
                        type=models.ScalarType.INT8, always_ram=True
                    )
                ),
            )
        self._ensure_indexes_sync(client)
        if self._store is None:
            self._store = QdrantVectorStore(
                client=client,
                collection_name=self.collection,
                embedding=self.embeddings,
                sparse_embedding=self.sparse,
                retrieval_mode=RetrievalMode.HYBRID,
                vector_name=DENSE,
                sparse_vector_name=SPARSE,
            )

    def _ensure_indexes_sync(self, client: QdrantClient) -> None:
        """Bring the collection's payload indexes up to `_INDEXED_FIELDS`.

        Deliberately OUTSIDE the create-collection branch. A collection created
        by an earlier version of this file, or by hand, or before a field joined
        a filter, exists but is missing indexes, and a create-time-only pass can
        never repair it -- which is exactly how a live cluster ended up rejecting
        every retrieval on `metadata.embedding_signature`. Running it on each
        setup makes the operation converge instead of depending on when the
        collection happened to be born.

        Existing indexes are skipped rather than recreated, so the common startup
        costs one `get_collection` call. A failure is logged and swallowed: an
        index is an optimisation on a self-hosted server and only a hard
        requirement under strict mode, so refusing to start would be worse than
        the degraded read it protects.
        """
        try:
            existing = set(client.get_collection(self.collection).payload_schema or {})
        except Exception:
            existing = set()
        for field in _INDEXED_FIELDS:
            if field in existing:
                continue
            try:
                client.create_payload_index(
                    collection_name=self.collection,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
            except Exception:
                log.warning("qdrant payload index not created", extra={"field": field})

    async def _ensure_ready(self) -> QdrantVectorStore:
        if not self._ready:
            async with _get_setup_lock():
                if not self._ready:
                    await asyncio.to_thread(self._ensure_collection_sync)
                    self._ready = True
        assert self._store is not None
        return self._store

    # ---- payload tagging + filters ----
    @staticmethod
    def _tag(
        chunks: list[Document],
        user_key: str | None,
        project_id: str | None,
        embedding_signature: str | None,
    ) -> list[Document]:
        for chunk in chunks:
            chunk.metadata["user_key"] = user_key or chunk.metadata.get("user_key") or "default"
            if project_id is not None:
                chunk.metadata["project_id"] = project_id
            if embedding_signature is not None:
                chunk.metadata["embedding_signature"] = embedding_signature
        return chunks

    @staticmethod
    def _filter(
        user_key: str | None = None,
        project_id: str | None = None,
        embedding_signature: str | None = None,
    ) -> models.Filter | None:
        conditions: list[models.Condition] = [
            models.FieldCondition(key=field, match=models.MatchValue(value=value))
            for field, value in (
                (_USER_KEY, user_key),
                (_PROJECT_ID, project_id),
                (_SIGNATURE, embedding_signature),
            )
            if value is not None
        ]
        return models.Filter(must=conditions) if conditions else None

    def _delete_by_filter_sync(self, qfilter: models.Filter) -> None:
        self._sync_client().delete(
            collection_name=self.collection,
            points_selector=models.FilterSelector(filter=qfilter),
        )

    # ---- VectorBackend interface ----
    async def index(
        self,
        chunks: list[Document],
        *,
        source_names: list[str] | None = None,
        persona: str = "",
        user_key: str | None = None,
        project_id: str | None = None,
        embedding_signature: str | None = None,
    ) -> dict[str, Any] | None:
        # Replace-semantics parity with FaissBackend.index(), but scoped: drop only
        # this (user_key, project_id) partition so a rebuild never duplicates its own
        # vectors and never touches another tenant's/project's data.
        store = await self._ensure_ready()
        scope = self._filter(user_key=user_key or "default", project_id=project_id)
        assert scope is not None
        await asyncio.to_thread(self._delete_by_filter_sync, scope)
        if not chunks:
            return await asyncio.to_thread(self.metadata)
        await asyncio.to_thread(
            store.add_documents,
            self._tag(list(chunks), user_key, project_id, embedding_signature),
        )
        return await asyncio.to_thread(self.metadata)

    async def add(
        self,
        chunks: list[Document],
        *,
        source_names: list[str] | None = None,
        persona: str = "",
        user_key: str | None = None,
        project_id: str | None = None,
        embedding_signature: str | None = None,
    ) -> dict[str, Any] | None:
        if not chunks:
            return await asyncio.to_thread(self.metadata)
        store = await self._ensure_ready()
        await asyncio.to_thread(
            store.add_documents,
            self._tag(list(chunks), user_key, project_id, embedding_signature),
        )
        return await asyncio.to_thread(self.metadata)

    async def remove(self, source: str) -> dict[str, Any] | None:
        await self._ensure_ready()
        qfilter = models.Filter(
            must=[models.FieldCondition(key=_SOURCE, match=models.MatchValue(value=source))]
        )
        await asyncio.to_thread(self._delete_by_filter_sync, qfilter)
        return await asyncio.to_thread(self.metadata)

    def _retrieve_sync(
        self,
        store: QdrantVectorStore,
        query: str,
        resolved_k: int,
        qfilter: models.Filter | None,
        threshold: float | None,
    ) -> list[tuple[Document, float | None]]:
        scored = store.similarity_search_with_score(query, k=resolved_k, filter=qfilter)
        if threshold and threshold > 0:
            scored = [(d, s) for d, s in scored if s >= threshold]
        # Same float() as FaissBackend._retrieve_sync. The two backends must not
        # differ in the type they hand back, or a bug ships on one and not the other.
        return [(d, float(s)) for d, s in scored]

    async def retrieve(
        self,
        query: str,
        *,
        k: int | None = None,
        search_type: str | None = None,
        min_score: float | None = None,
        user_key: str | None = None,
        project_id: str | None = None,
        embedding_signature: str | None = None,
    ) -> list[tuple[Document, float | None]]:
        # search_type is ignored: HYBRID always runs dense + sparse and fuses (RRF).
        store = await self._ensure_ready()
        resolved_k = max(k or self.settings.top_k, 1)
        qfilter = self._filter(user_key, project_id, embedding_signature)
        threshold = self.settings.score_threshold if min_score is None else min_score
        return await asyncio.to_thread(
            self._retrieve_sync, store, query, resolved_k, qfilter, threshold
        )

    def clear_project(self, user_key: str | None, project_id: str) -> None:
        qfilter = self._filter(user_key=user_key, project_id=project_id)
        if qfilter is None:
            return
        if self._sync_client().collection_exists(self.collection):
            self._delete_by_filter_sync(qfilter)

    def exists(self) -> bool:
        try:
            return self._sync_client().collection_exists(self.collection)
        except Exception:
            return False

    def metadata(self) -> dict[str, Any] | None:
        try:
            client = self._sync_client()
            if not client.collection_exists(self.collection):
                return None
            info = client.get_collection(self.collection)
            return {
                "embedding_provider": self.settings.embedding_provider,
                "embedding_model": self.settings.embedding_model,
                "chunk_size": self.settings.chunk_size,
                "chunk_overlap": self.settings.chunk_overlap,
                "chunk_count": info.points_count or 0,
                "backend": "qdrant",
                "collection": self.collection,
            }
        except Exception:
            return None

    def invalidate_cache(self) -> None:
        # Qdrant holds no local index handle to refresh (unlike FAISS); reads always
        # hit the server. Keep the collection/store; nothing to drop.
        return None

    def reset(self) -> None:
        try:
            client = self._sync_client()
            if client.collection_exists(self.collection):
                client.delete_collection(self.collection)
        except Exception:
            pass
        self._store = None
        self._ready = False
