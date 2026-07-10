from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.documents import Document
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient, models

from logic.config import RAGSettings

DENSE = "dense"
SPARSE = "sparse"

# Payload field paths. langchain-qdrant nests a document's metadata under a
# "metadata" key in the point payload, so every tenant/project filter targets
# "metadata.<field>" (verified against langchain-qdrant 0.2.1).
_USER_KEY = "metadata.user_key"
_PROJECT_ID = "metadata.project_id"
_SIGNATURE = "metadata.embedding_signature"
_SOURCE = "metadata.source"

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

    def __init__(self, settings: RAGSettings, embeddings, *, location: str | None = None):
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
                vectors_config={DENSE: models.VectorParams(size=dim, distance=models.Distance.COSINE)},
                sparse_vectors_config={SPARSE: models.SparseVectorParams()},
                hnsw_config=models.HnswConfigDiff(m=16, ef_construct=100),
                quantization_config=models.ScalarQuantization(
                    scalar=models.ScalarQuantizationConfig(
                        type=models.ScalarType.INT8, always_ram=True
                    )
                ),
            )
            # Keyword indexes make the tenant/project filters index-accelerated on a
            # Qdrant server (no-op in local mode, so tests just warn).
            for field in (_USER_KEY, _PROJECT_ID):
                client.create_payload_index(
                    collection_name=self.collection, field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
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
    def _tag(chunks: list[Document], project_id, embedding_signature) -> list[Document]:
        for chunk in chunks:
            chunk.metadata["user_key"] = chunk.metadata.get("user_key") or "default"
            if project_id is not None:
                chunk.metadata["project_id"] = project_id
            if embedding_signature is not None:
                chunk.metadata["embedding_signature"] = embedding_signature
        return chunks

    @staticmethod
    def _filter(user_key=None, project_id=None, embedding_signature=None) -> models.Filter | None:
        conditions = [
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
    async def index(self, chunks, *, source_names=None, persona="",
                    project_id=None, embedding_signature=None) -> dict[str, Any] | None:
        # Replace-semantics parity with FaissBackend.index(), but scoped: drop only
        # this (user_key, project_id) partition so a rebuild never duplicates its own
        # vectors and never touches another tenant's/project's data.
        store = await self._ensure_ready()
        scope = self._filter(user_key="default", project_id=project_id)
        await asyncio.to_thread(self._delete_by_filter_sync, scope)
        if not chunks:
            return self.metadata()
        await asyncio.to_thread(
            store.add_documents, self._tag(list(chunks), project_id, embedding_signature)
        )
        return self.metadata()

    async def add(self, chunks, *, source_names=None, persona="",
                  project_id=None, embedding_signature=None) -> dict[str, Any] | None:
        if not chunks:
            return self.metadata()
        store = await self._ensure_ready()
        await asyncio.to_thread(
            store.add_documents, self._tag(list(chunks), project_id, embedding_signature)
        )
        return self.metadata()

    async def remove(self, source: str) -> dict[str, Any] | None:
        await self._ensure_ready()
        qfilter = models.Filter(must=[models.FieldCondition(
            key=_SOURCE, match=models.MatchValue(value=source))])
        await asyncio.to_thread(self._delete_by_filter_sync, qfilter)
        return self.metadata()

    def _retrieve_sync(self, store, query, resolved_k, qfilter, threshold):
        scored = store.similarity_search_with_score(query, k=resolved_k, filter=qfilter)
        if threshold and threshold > 0:
            scored = [(d, s) for d, s in scored if s >= threshold]
        return scored

    async def retrieve(self, query, *, k=None, search_type=None, min_score=None,
                       user_key=None, project_id=None, embedding_signature=None):
        # search_type is ignored: HYBRID always runs dense + sparse and fuses (RRF).
        store = await self._ensure_ready()
        resolved_k = max(k or self.settings.top_k, 1)
        qfilter = self._filter(user_key, project_id, embedding_signature)
        threshold = self.settings.score_threshold if min_score is None else min_score
        return await asyncio.to_thread(
            self._retrieve_sync, store, query, resolved_k, qfilter, threshold
        )

    def clear_project(self, user_key, project_id) -> None:
        qfilter = self._filter(user_key=user_key, project_id=project_id)
        if qfilter is None:
            return
        try:
            if self._sync_client().collection_exists(self.collection):
                self._delete_by_filter_sync(qfilter)
        except Exception:
            pass

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
