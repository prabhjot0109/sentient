from __future__ import annotations

import unittest
from typing import cast

from logic.ingestion import ArchivesIngestion
from logic.retrieval.base import VectorBackend


class IngestionRetrieveForwardTests(unittest.IsolatedAsyncioTestCase):
    async def test_retrieve_forwards_project_id_and_embedding_signature(self):
        captured: dict = {}

        class _FakeBackend:
            async def retrieve(self, query, **kwargs):
                captured["query"] = query
                captured.update(kwargs)
                return []

        archives = object.__new__(ArchivesIngestion)
        archives.backend = cast(VectorBackend, _FakeBackend())

        await archives.retrieve(
            "hail the jarl",
            k=4,
            search_type="similarity",
            min_score=0.1,
            user_key="tenant-a",
            project_id="proj-skyrim",
            embedding_signature="google:emb-001",
        )

        self.assertEqual(captured["query"], "hail the jarl")
        self.assertEqual(captured["user_key"], "tenant-a")
        self.assertEqual(captured["project_id"], "proj-skyrim")
        self.assertEqual(captured["embedding_signature"], "google:emb-001")
        self.assertEqual(captured["k"], 4)
        self.assertEqual(captured["search_type"], "similarity")
        self.assertEqual(captured["min_score"], 0.1)


if __name__ == "__main__":
    unittest.main()
