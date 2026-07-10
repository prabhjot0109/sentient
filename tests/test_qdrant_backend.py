from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from logic.config import load_rag_settings


class _FakeDense(Embeddings):
    """8-dim deterministic dense vectors so :memory: Qdrant can index them
    without a network embedding call."""

    def embed_query(self, text: str):
        low = text.lower()
        return [float((sum(ord(c) for c in low) >> i) % 17) for i in range(8)]

    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]


def _qdrant_settings():
    with patch.dict(os.environ, {"VECTOR_BACKEND": "qdrant", "RAG_HYBRID": "true"}, clear=False):
        return load_rag_settings()


class QdrantBackendTests(unittest.IsolatedAsyncioTestCase):
    async def test_index_and_hybrid_retrieve(self):
        from logic.retrieval.qdrant_store import QdrantBackend

        backend = QdrantBackend(_qdrant_settings(), _FakeDense(), location=":memory:")
        await backend.index([
            Document(page_content="Nords have frost resistance and two-handed skill.",
                     metadata={"source": "skills.pdf", "chunk_id": 0}),
            Document(page_content="The city of Whiterun sits in the tundra.",
                     metadata={"source": "places.pdf", "chunk_id": 1}),
        ])
        results = await backend.retrieve("Nord frost resistance", k=2, min_score=0.0)
        self.assertTrue(results)
        self.assertIsInstance(results[0][0], Document)

    async def test_user_key_isolation(self):
        from logic.retrieval.qdrant_store import QdrantBackend

        backend = QdrantBackend(_qdrant_settings(), _FakeDense(), location=":memory:")
        await backend.add([Document(page_content="tenant A lore",
                                    metadata={"source": "a.txt", "user_key": "A"})])
        await backend.add([Document(page_content="tenant B lore",
                                    metadata={"source": "b.txt", "user_key": "B"})])
        a_hits = await backend.retrieve("lore", k=5, min_score=0.0, user_key="A")
        sources = {d.metadata.get("source") for d, _ in a_hits}
        self.assertIn("a.txt", sources)
        self.assertNotIn("b.txt", sources)

    async def test_project_id_isolation_and_clear(self):
        from logic.retrieval.qdrant_store import QdrantBackend

        backend = QdrantBackend(_qdrant_settings(), _FakeDense(), location=":memory:")
        await backend.add([Document(page_content="skyrim lore", metadata={"source": "sky.txt"})],
                          project_id="skyrim")
        await backend.add([Document(page_content="fallout lore", metadata={"source": "fo.txt"})],
                          project_id="fallout")

        skyrim = await backend.retrieve("lore", k=5, min_score=0.0, project_id="skyrim")
        self.assertEqual({d.metadata.get("source") for d, _ in skyrim}, {"sky.txt"})

        backend.clear_project(None, "skyrim")
        after = await backend.retrieve("lore", k=5, min_score=0.0, project_id="skyrim")
        self.assertEqual(after, [])
        # The other project is untouched.
        fallout = await backend.retrieve("lore", k=5, min_score=0.0, project_id="fallout")
        self.assertEqual({d.metadata.get("source") for d, _ in fallout}, {"fo.txt"})

    async def test_embedding_signature_filters_stale_vectors(self):
        from logic.retrieval.qdrant_store import QdrantBackend

        backend = QdrantBackend(_qdrant_settings(), _FakeDense(), location=":memory:")
        await backend.add([Document(page_content="v1 lore", metadata={"source": "v1.txt"})],
                          embedding_signature="sig-v1")
        # A query stamped with the current signature only sees current-signature vectors.
        hits = await backend.retrieve("lore", k=5, min_score=0.0, embedding_signature="sig-v1")
        self.assertEqual({d.metadata.get("source") for d, _ in hits}, {"v1.txt"})
        stale = await backend.retrieve("lore", k=5, min_score=0.0, embedding_signature="sig-v2")
        self.assertEqual(stale, [])

    async def test_remove_source_drops_chunks(self):
        from logic.retrieval.qdrant_store import QdrantBackend

        backend = QdrantBackend(_qdrant_settings(), _FakeDense(), location=":memory:")
        await backend.add([
            Document(page_content="alpha", metadata={"source": "a.txt"}),
            Document(page_content="beta", metadata={"source": "b.txt"}),
        ])
        await backend.remove("a.txt")
        sources = {d.metadata.get("source") for d, _ in await backend.retrieve("alpha beta", k=5, min_score=0.0)}
        self.assertNotIn("a.txt", sources)


if __name__ == "__main__":
    unittest.main()
