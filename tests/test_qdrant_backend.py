from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from sentient.core.config import load_rag_settings


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
        from sentient.adapters.retrieval.qdrant_store import QdrantBackend

        backend = QdrantBackend(_qdrant_settings(), _FakeDense(), location=":memory:")
        await backend.index(
            [
                Document(
                    page_content="Nords have frost resistance and two-handed skill.",
                    metadata={"source": "skills.pdf", "chunk_id": 0},
                ),
                Document(
                    page_content="The city of Whiterun sits in the tundra.",
                    metadata={"source": "places.pdf", "chunk_id": 1},
                ),
            ]
        )
        results = await backend.retrieve("Nord frost resistance", k=2, min_score=0.0)
        self.assertTrue(results)
        self.assertIsInstance(results[0][0], Document)

    async def test_user_key_isolation(self):
        from sentient.adapters.retrieval.qdrant_store import QdrantBackend

        backend = QdrantBackend(_qdrant_settings(), _FakeDense(), location=":memory:")
        await backend.add(
            [Document(page_content="tenant A lore", metadata={"source": "a.txt", "user_key": "A"})]
        )
        await backend.add(
            [Document(page_content="tenant B lore", metadata={"source": "b.txt", "user_key": "B"})]
        )
        a_hits = await backend.retrieve("lore", k=5, min_score=0.0, user_key="A")
        sources = {d.metadata.get("source") for d, _ in a_hits}
        self.assertIn("a.txt", sources)
        self.assertNotIn("b.txt", sources)

    async def test_explicit_user_key_overrides_document_metadata(self):
        from sentient.adapters.retrieval.qdrant_store import QdrantBackend

        backend = QdrantBackend(_qdrant_settings(), _FakeDense(), location=":memory:")
        await backend.add(
            [
                Document(
                    page_content="tenant A lore", metadata={"source": "a.txt", "user_key": "stale"}
                )
            ],
            user_key="tenant-a",
        )

        tenant_hits = await backend.retrieve("lore", k=5, min_score=0.0, user_key="tenant-a")
        stale_hits = await backend.retrieve("lore", k=5, min_score=0.0, user_key="stale")
        self.assertEqual({d.metadata.get("source") for d, _ in tenant_hits}, {"a.txt"})
        self.assertEqual(stale_hits, [])

    async def test_index_replaces_only_requested_user_project_scope(self):
        from sentient.adapters.retrieval.qdrant_store import QdrantBackend

        backend = QdrantBackend(_qdrant_settings(), _FakeDense(), location=":memory:")
        await backend.add(
            [Document(page_content="old tenant A lore", metadata={"source": "old-a.txt"})],
            user_key="tenant-a",
            project_id="shared",
        )
        await backend.add(
            [Document(page_content="tenant B lore", metadata={"source": "b.txt"})],
            user_key="tenant-b",
            project_id="shared",
        )
        await backend.index(
            [Document(page_content="new tenant A lore", metadata={"source": "new-a.txt"})],
            user_key="tenant-a",
            project_id="shared",
        )

        tenant_a = await backend.retrieve(
            "lore", k=5, min_score=0.0, user_key="tenant-a", project_id="shared"
        )
        tenant_b = await backend.retrieve(
            "lore", k=5, min_score=0.0, user_key="tenant-b", project_id="shared"
        )
        self.assertEqual({d.metadata.get("source") for d, _ in tenant_a}, {"new-a.txt"})
        self.assertEqual({d.metadata.get("source") for d, _ in tenant_b}, {"b.txt"})

    async def test_project_id_isolation_and_clear(self):
        from sentient.adapters.retrieval.qdrant_store import QdrantBackend

        backend = QdrantBackend(_qdrant_settings(), _FakeDense(), location=":memory:")
        await backend.add(
            [Document(page_content="skyrim lore", metadata={"source": "sky.txt"})],
            project_id="skyrim",
        )
        await backend.add(
            [Document(page_content="fallout lore", metadata={"source": "fo.txt"})],
            project_id="fallout",
        )

        skyrim = await backend.retrieve("lore", k=5, min_score=0.0, project_id="skyrim")
        self.assertEqual({d.metadata.get("source") for d, _ in skyrim}, {"sky.txt"})

        backend.clear_project(None, "skyrim")
        after = await backend.retrieve("lore", k=5, min_score=0.0, project_id="skyrim")
        self.assertEqual(after, [])
        # The other project is untouched.
        fallout = await backend.retrieve("lore", k=5, min_score=0.0, project_id="fallout")
        self.assertEqual({d.metadata.get("source") for d, _ in fallout}, {"fo.txt"})

    async def test_embedding_signature_filters_stale_vectors(self):
        from sentient.adapters.retrieval.qdrant_store import QdrantBackend

        backend = QdrantBackend(_qdrant_settings(), _FakeDense(), location=":memory:")
        await backend.add(
            [Document(page_content="v1 lore", metadata={"source": "v1.txt"})],
            embedding_signature="sig-v1",
        )
        # A query stamped with the current signature only sees current-signature vectors.
        hits = await backend.retrieve("lore", k=5, min_score=0.0, embedding_signature="sig-v1")
        self.assertEqual({d.metadata.get("source") for d, _ in hits}, {"v1.txt"})
        stale = await backend.retrieve("lore", k=5, min_score=0.0, embedding_signature="sig-v2")
        self.assertEqual(stale, [])

    async def test_remove_source_drops_chunks(self):
        from sentient.adapters.retrieval.qdrant_store import QdrantBackend

        backend = QdrantBackend(_qdrant_settings(), _FakeDense(), location=":memory:")
        await backend.add(
            [
                Document(page_content="alpha", metadata={"source": "a.txt"}),
                Document(page_content="beta", metadata={"source": "b.txt"}),
            ]
        )
        await backend.remove("a.txt")
        sources = {
            d.metadata.get("source")
            for d, _ in await backend.retrieve("alpha beta", k=5, min_score=0.0)
        }
        self.assertNotIn("a.txt", sources)


class QdrantPayloadIndexTests(unittest.TestCase):
    """Every filtered field must be indexed, on a collection that already exists.

    A Qdrant Cloud cluster runs strict mode, where a filter on an unindexed
    payload field is refused with INVALID_ARGUMENT rather than answered slowly.
    `services/chat._retrieve` catches that and answers ungrounded, so the whole
    failure surfaces to a player as an NPC that ignores its own lore.
    """

    def _backend(self):
        from sentient.adapters.retrieval.qdrant_store import QdrantBackend

        return QdrantBackend(_qdrant_settings(), _FakeDense(), location=":memory:")

    def test_missing_indexes_are_created_on_an_existing_collection(self):
        from sentient.adapters.retrieval import qdrant_store

        client = MagicMock()
        client.collection_exists.return_value = True
        client.get_collection.return_value = SimpleNamespace(
            payload_schema={"metadata.user_key": object()}
        )
        backend = self._backend()
        # Pre-set so `_ensure_collection_sync` skips building a QdrantVectorStore,
        # which would introspect the mock's collection config. The store is not
        # what this test is about.
        backend._store = MagicMock()
        with patch.object(backend, "_sync_client", return_value=client):
            backend._ensure_collection_sync()

        client.create_collection.assert_not_called()
        indexed = {c.kwargs["field_name"] for c in client.create_payload_index.call_args_list}
        self.assertEqual(
            indexed,
            {
                qdrant_store._PROJECT_ID,
                qdrant_store._SIGNATURE,
                qdrant_store._SOURCE,
            },
        )

    def test_index_creation_failure_does_not_block_startup(self):
        client = MagicMock()
        client.get_collection.side_effect = RuntimeError("no such collection")
        client.create_payload_index.side_effect = RuntimeError("refused")
        backend = self._backend()
        backend._ensure_indexes_sync(client)
        self.assertEqual(client.create_payload_index.call_count, 4)


class QdrantFactoryTests(unittest.TestCase):
    def test_factory_returns_qdrant_backend(self):
        from sentient.adapters.retrieval.factory import get_vector_backend
        from sentient.adapters.retrieval.qdrant_store import QdrantBackend

        with patch.dict(
            os.environ, {"VECTOR_BACKEND": "qdrant", "QDRANT_URL": "http://x:6333"}, clear=False
        ):
            settings = load_rag_settings()
        backend = get_vector_backend(settings, None, _FakeDense())
        self.assertIsInstance(backend, QdrantBackend)


if __name__ == "__main__":
    unittest.main()
