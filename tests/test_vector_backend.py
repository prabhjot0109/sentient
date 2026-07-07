from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from logic.config import load_rag_settings
from logic.retrieval.base import VectorBackend
from logic.retrieval.faiss_store import FaissBackend


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


class _FakeEmbeddings(Embeddings):
    def embed_query(self, text: str) -> list[float]:
        low = text.lower()
        return [float(sum(ord(c) for c in low) % 997), float(len(low)), float(low.count("guard") * 10)]
    def embed_documents(self, texts): return [self.embed_query(t) for t in texts]


class FaissBackendTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.index_path = Path(self.tmp.name) / "faiss_index"

    def tearDown(self):
        self.tmp.cleanup()

    def _backend(self):
        return FaissBackend(load_rag_settings(), self.index_path, _FakeEmbeddings())

    async def test_index_then_retrieve_roundtrip(self):
        backend = self._backend()
        await backend.index([
            Document(page_content="Sentinel guards the archives.",
                     metadata={"source": "lore.txt", "chunk_id": 0}),
            Document(page_content="Nords have frost resistance.",
                     metadata={"source": "lore.txt", "chunk_id": 1}),
        ])
        self.assertTrue(backend.exists())
        results = await backend.retrieve("who guards the archives", k=2,
                                         search_type="similarity", min_score=0.0)
        self.assertTrue(results)
        self.assertIsInstance(results[0][0], Document)

    async def test_remove_source_drops_chunks(self):
        backend = self._backend()
        await backend.index([
            Document(page_content="a", metadata={"source": "a.txt", "chunk_id": 0}),
            Document(page_content="b", metadata={"source": "b.txt", "chunk_id": 1}),
        ])
        await backend.remove("a.txt")
        backend.invalidate_cache()
        got = {d.metadata.get("source") for d, _ in await backend.retrieve("x", k=10, min_score=0.0)}
        self.assertNotIn("a.txt", got)


if __name__ == "__main__":
    unittest.main()
