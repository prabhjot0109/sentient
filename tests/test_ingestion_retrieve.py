from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import cast

from langchain_core.documents import Document

from sentient.adapters.documents import ArchivesIngestion
from sentient.adapters.retrieval.base import VectorBackend


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

    async def test_add_file_forwards_write_scope(self):
        captured: dict = {}

        class _FakeBackend:
            def metadata(self):
                return {"persona": "existing"}

            async def add(self, chunks, **kwargs):
                captured["chunks"] = chunks
                captured.update(kwargs)
                return {"chunk_count": 12}

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lore.txt"
            path.write_text("Scoped lore", encoding="utf-8")
            archives = object.__new__(ArchivesIngestion)
            archives.backend = cast(VectorBackend, _FakeBackend())
            archives.data_dir = Path(tmp)
            archives._load_file = lambda _path: [
                Document(page_content="Scoped lore", metadata={"source": "lore.txt"})
            ]
            archives._split_documents = lambda documents: documents
            archives._resolve_source_files = lambda source_path=None: [path]

            result = await archives.add_file(
                str(path),
                user_key="tenant-a",
                project_id="project-a",
                embedding_signature="sig-a",
            )

        self.assertEqual(captured["user_key"], "tenant-a")
        self.assertEqual(captured["project_id"], "project-a")
        self.assertEqual(captured["embedding_signature"], "sig-a")
        self.assertEqual(result["added_chunk_count"], 1)


if __name__ == "__main__":
    unittest.main()
