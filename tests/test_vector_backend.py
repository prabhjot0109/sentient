from __future__ import annotations

import os
import unittest
from typing import Any
from unittest.mock import patch

from langchain_core.documents import Document

from logic.retrieval.base import VectorBackend


class _FakeBackend:
    def __init__(self) -> None:
        self._docs: list[Document] = []

    async def index(self, chunks, *, project_id=None, embedding_signature=None):
        self._docs = list(chunks); return {"chunk_count": len(self._docs)}
    async def add(self, chunks, *, project_id=None, embedding_signature=None):
        self._docs.extend(chunks); return {"chunk_count": len(self._docs)}
    async def remove(self, source):
        self._docs = [d for d in self._docs if d.metadata.get("source") != source]
        return {"chunk_count": len(self._docs)}
    async def retrieve(self, query, *, k=None, search_type=None, min_score=None,
                       user_key=None, project_id=None, embedding_signature=None):
        return [(d, 1.0) for d in self._docs[: (k or 4)]]
    def exists(self): return bool(self._docs)
    def metadata(self): return {"chunk_count": len(self._docs)}
    def invalidate_cache(self): pass
    def reset(self): self._docs = []
    def clear_project(self, user_key, project_id): pass


class VectorBackendProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_fake_backend_satisfies_protocol(self):
        backend: VectorBackend = _FakeBackend()
        await backend.index([Document(page_content="a", metadata={"source": "x"})])
        self.assertTrue(backend.exists())
        results = await backend.retrieve("q", k=1)
        self.assertEqual(len(results), 1)

    def test_isinstance_runtime_checkable(self):
        self.assertIsInstance(_FakeBackend(), VectorBackend)


if __name__ == "__main__":
    unittest.main()
