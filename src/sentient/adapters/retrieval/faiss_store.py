from __future__ import annotations

import asyncio
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_community.vectorstores import FAISS

from sentient.core.config import RAGSettings

MANIFEST_FILE = "manifest.json"

# One asyncio.Lock per event loop. asyncio.Lock is NOT thread-safe and binds to a
# loop, so a single module-level instance breaks across test loops; key by loop id.
_index_locks: dict[int, asyncio.Lock] = {}


def _get_index_lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    lock = _index_locks.get(id(loop))
    if lock is None:
        lock = asyncio.Lock()
        _index_locks[id(loop)] = lock
    return lock


class FaissBackend:
    """FAISS impl of VectorBackend. Single-tenant, single-project: ignores
    user_key/project_id/embedding_signature. Sync FAISS calls are offloaded with
    asyncio.to_thread; writes serialized by an asyncio.Lock."""

    def __init__(self, settings: RAGSettings, index_path, embeddings) -> None:
        self.settings = settings
        self.index_path = Path(index_path)
        self.embeddings = embeddings
        self._store: FAISS | None = None

    @property
    def manifest_path(self) -> Path:
        return self.index_path / MANIFEST_FILE

    def metadata(self) -> dict[str, Any] | None:
        if not self.manifest_path.exists():
            return None
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def _manifest_matches_runtime(self, manifest) -> bool:
        return bool(manifest) and (
            manifest.get("embedding_provider") == self.settings.embedding_provider
            and manifest.get("embedding_model") == self.settings.embedding_model
            and manifest.get("chunk_size") == self.settings.chunk_size
            and manifest.get("chunk_overlap") == self.settings.chunk_overlap
        )

    def _write_manifest(self, *, source_names, chunk_count, persona) -> dict[str, Any]:
        manifest = {
            "embedding_provider": self.settings.embedding_provider,
            "embedding_model": self.settings.embedding_model,
            "chunk_size": self.settings.chunk_size,
            "chunk_overlap": self.settings.chunk_overlap,
            "source_count": len(source_names),
            "chunk_count": chunk_count,
            "sources": source_names,
            "persona": persona,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        self.index_path.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8"
        )
        return manifest

    def invalidate_cache(self) -> None:
        self._store = None

    def reset(self) -> None:
        self._store = None
        if self.index_path.exists():
            shutil.rmtree(self.index_path)

    def clear_project(self, user_key, project_id) -> None:
        # FAISS is single-project: nothing to partition. No-op (Qdrant impl in Plan 02).
        return None

    def exists(self) -> bool:
        return self.index_path.exists() and self.manifest_path.exists()

    def _load_sync(self) -> FAISS | None:
        manifest = self.metadata()
        if not self.index_path.exists() or not self._manifest_matches_runtime(manifest):
            self._store = None
            return None
        if self._store is None:
            self._store = FAISS.load_local(
                str(self.index_path), self.embeddings, allow_dangerous_deserialization=True
            )
        return self._store

    # ---- write ops (each blocking part offloaded; the async wrapper holds the lock) ----
    def _index_sync(self, chunks, source_names, persona):
        db = FAISS.from_documents(chunks, self.embeddings)
        self.reset()
        self.index_path.mkdir(parents=True, exist_ok=True)
        db.save_local(str(self.index_path))
        self._store = db
        names = source_names or sorted({c.metadata.get("source", "unknown") for c in chunks})
        return self._write_manifest(
            source_names=list(names), chunk_count=len(chunks), persona=persona
        )

    async def index(
        self,
        chunks,
        *,
        source_names=None,
        persona="",
        user_key=None,
        project_id=None,
        embedding_signature=None,
    ) -> dict[str, Any] | None:
        if not chunks:
            self.reset()
            return None
        async with _get_index_lock():
            return await asyncio.to_thread(self._index_sync, chunks, source_names, persona)

    def _add_sync(self, chunks, source_names, persona):
        new_store = FAISS.from_documents(chunks, self.embeddings)
        existing = self._load_sync()
        if existing is not None:
            existing.merge_from(new_store)
            db = existing
        else:
            db = new_store
        self.index_path.mkdir(parents=True, exist_ok=True)
        db.save_local(str(self.index_path))
        self._store = db
        manifest = self.metadata() or {}
        names = source_names or manifest.get("sources", [])
        total = manifest.get("chunk_count", 0) + len(chunks)
        return self._write_manifest(
            source_names=list(names),
            chunk_count=total,
            persona=persona or manifest.get("persona", ""),
        )

    async def add(
        self,
        chunks,
        *,
        source_names=None,
        persona="",
        user_key=None,
        project_id=None,
        embedding_signature=None,
    ) -> dict[str, Any] | None:
        if not chunks:
            return self.metadata()
        async with _get_index_lock():
            return await asyncio.to_thread(self._add_sync, chunks, source_names, persona)

    def _remove_sync(self, source):
        store = self._load_sync()
        manifest = self.metadata() or {}
        if store is None:
            return manifest or None
        ids = [i for i, d in store.docstore._dict.items() if d.metadata.get("source") == source]
        remaining = [n for n in manifest.get("sources", []) if n != source]
        if not remaining:
            self.reset()
            return None
        if ids:
            store.delete(ids)
        self.index_path.mkdir(parents=True, exist_ok=True)
        store.save_local(str(self.index_path))
        self._store = store
        total = max(manifest.get("chunk_count", 0) - len(ids), 0)
        return self._write_manifest(
            source_names=remaining, chunk_count=total, persona=manifest.get("persona", "")
        )

    async def remove(self, source) -> dict[str, Any] | None:
        async with _get_index_lock():
            return await asyncio.to_thread(self._remove_sync, source)

    # ---- read ----
    def _retrieve_sync(self, query, k, search_type, min_score):
        store = self._load_sync()
        if store is None:
            return []
        resolved_k = max(k or self.settings.top_k, 1)
        resolved_type = (search_type or self.settings.search_type).lower()
        threshold = self.settings.score_threshold if min_score is None else min_score
        if resolved_type == "similarity":
            try:
                scored = store.similarity_search_with_relevance_scores(query, k=resolved_k)
            except Exception:
                return [(d, None) for d in store.similarity_search(query, k=resolved_k)]
            if threshold > 0:
                scored = [(d, s) for d, s in scored if s >= threshold]
            return scored
        fetch_k = max(self.settings.fetch_k, resolved_k)
        docs = store.max_marginal_relevance_search(
            query, k=resolved_k, fetch_k=fetch_k, lambda_mult=self.settings.lambda_mult
        )
        return [(d, None) for d in docs]

    async def retrieve(
        self,
        query,
        *,
        k=None,
        search_type=None,
        min_score=None,
        user_key=None,
        project_id=None,
        embedding_signature=None,
    ):
        return await asyncio.to_thread(self._retrieve_sync, query, k, search_type, min_score)
