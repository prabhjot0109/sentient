from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sentient.core.concurrency import ReindexJob
from sentient.core.errors import SourceFilesMissing
from sentient.services import ingestion


@dataclass
class FakeSettings:
    vector_backend: str = "qdrant"


class FakeArchives:
    """Enough of ArchivesIngestion for run_reindex_job, and it records order.

    The ordering is the whole point of these tests: `clear_project` and
    `reset_index` destroy the project's vectors, and whether they ran before the
    job discovered it could not finish is the difference between a refusal and
    data loss.
    """

    def __init__(self, data_dir: Path, *, backend: str = "qdrant") -> None:
        self.data_dir = data_dir
        self.settings = FakeSettings(vector_backend=backend)
        self.calls: list[str] = []

    def clear_project(self, user_key: str | None, project_id: str) -> None:
        self.calls.append("clear_project")

    def reset_index(self) -> None:
        self.calls.append("reset_index")

    async def add_file(self, path: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(f"add_file:{Path(path).name}")
        return {"added_chunk_count": 3}


class FakeStore:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents
        self.document_status: dict[str, str] = {}
        self.project_status: str | None = None
        self.reindex_error: str | None = None

    async def list_documents(self, project_id: str) -> list[dict[str, Any]]:
        return list(self.documents)

    async def set_document_status(self, project_id: str, filename: str, status: str) -> None:
        self.document_status[filename] = status

    async def register_document(self, project_id, filename, chunk_count, signature, status):
        self.document_status[filename] = status

    async def set_project_status(self, project_id: str, status: str) -> None:
        self.project_status = status

    async def set_reindex_error(self, project_id: str, error: str | None) -> None:
        self.reindex_error = error


class ReindexWithMissingSourcesTests(unittest.IsolatedAsyncioTestCase):
    """A reindex re-reads uploaded files from disk. They are not always there.

    `run_reindex_job` rebuilds every document by loading `data_dir/<filename>`
    again, so `data/` is an input to the rebuild and not a cache of it. On a host
    with no persistent disk that directory is empty after any restart, while the
    `documents` rows in Postgres and the vectors in Qdrant both survive -- so the
    rebuild is asked to re-read files that no longer exist.

    Before this guard the job cleared the project's vectors first and discovered
    the missing file afterwards, which destroyed a working index and left the
    project pinned at `reindexing_required`, answering 409 on every turn, with its
    document rows frozen at `reindexing`. That is a user-reachable path: changing
    the embedding model in project settings is what queues a reindex.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data_dir = Path(self.tmp.name)
        self.job = ReindexJob(
            project_id="project-1",
            user_key="user-1",
            api_key=None,
            embedding_signature="google:models/embedding-001",
        )

    def _write(self, filename: str) -> None:
        (self.data_dir / filename).write_text("lore", encoding="utf-8")

    async def test_a_missing_source_refuses_before_clearing_the_index(self):
        store = FakeStore([{"filename": "lore.txt"}])
        archives = FakeArchives(self.data_dir)

        with self.assertRaises(SourceFilesMissing):
            await ingestion.run_reindex_job(self.job, state_store=store, archives=archives)

        self.assertEqual(
            archives.calls,
            [],
            "the vectors were destroyed before the job noticed it could not rebuild them",
        )

    async def test_the_missing_document_is_marked_failed_not_left_reindexing(self):
        """`reindexing` is a transient status nothing reconciles.

        Startup reconciliation fails orphaned `processing` rows only, so a row left
        at `reindexing` stays there for good and the console renders a spinner that
        never resolves. `failed` is a status the document manager already draws.
        """
        store = FakeStore([{"filename": "lore.txt"}])
        archives = FakeArchives(self.data_dir)

        with self.assertRaises(SourceFilesMissing):
            await ingestion.run_reindex_job(self.job, state_store=store, archives=archives)

        self.assertEqual(store.document_status["lore.txt"], "failed")

    async def test_the_error_names_every_missing_file(self):
        store = FakeStore([{"filename": "lore.txt"}, {"filename": "atlas.pdf"}])
        archives = FakeArchives(self.data_dir)

        with self.assertRaises(SourceFilesMissing) as caught:
            await ingestion.run_reindex_job(self.job, state_store=store, archives=archives)

        message = str(caught.exception)
        self.assertIn("lore.txt", message)
        self.assertIn("atlas.pdf", message)

    async def test_a_present_file_is_not_marked_failed_alongside_a_missing_one(self):
        """Only the unreadable ones. Marking a healthy document failed would send
        the user to re-upload a file that is sitting right there."""
        self._write("present.txt")
        store = FakeStore([{"filename": "present.txt"}, {"filename": "gone.txt"}])
        archives = FakeArchives(self.data_dir)

        with self.assertRaises(SourceFilesMissing):
            await ingestion.run_reindex_job(self.job, state_store=store, archives=archives)

        self.assertEqual(store.document_status, {"gone.txt": "failed"})

    async def test_the_project_is_left_reindexing_required_so_a_retry_converges(self):
        """Honest rather than tidy.

        The config that queued this rebuild has already changed, so the surviving
        vectors carry the wrong embedding signature and retrieval against them is
        wrong. `reindexing_required` keeps the 409 guard up until the user
        re-uploads and reindexes, which the removal of the old status guard makes
        possible.
        """
        store = FakeStore([{"filename": "lore.txt"}])
        archives = FakeArchives(self.data_dir)

        with self.assertRaises(SourceFilesMissing):
            await ingestion.run_reindex_job(self.job, state_store=store, archives=archives)

        self.assertEqual(store.project_status, "reindexing_required")

    async def test_a_project_with_every_source_present_still_rebuilds(self):
        """The guard must not become the failure mode it prevents."""
        self._write("lore.txt")
        self._write("atlas.pdf")
        store = FakeStore([{"filename": "lore.txt"}, {"filename": "atlas.pdf"}])
        archives = FakeArchives(self.data_dir)

        await ingestion.run_reindex_job(self.job, state_store=store, archives=archives)

        self.assertEqual(store.project_status, "active")
        self.assertEqual(store.document_status, {"lore.txt": "ready", "atlas.pdf": "ready"})
        self.assertIn("clear_project", archives.calls)

    async def test_a_project_with_no_documents_still_rebuilds(self):
        store = FakeStore([])
        archives = FakeArchives(self.data_dir)

        await ingestion.run_reindex_job(self.job, state_store=store, archives=archives)

        self.assertEqual(store.project_status, "active")

    async def test_faiss_resets_the_index_only_after_the_guard_passes(self):
        """FAISS wipes a shared index file rather than deleting by filter, so the
        ordering matters more there, not less."""
        store = FakeStore([{"filename": "lore.txt"}])
        archives = FakeArchives(self.data_dir, backend="faiss")

        with self.assertRaises(SourceFilesMissing):
            await ingestion.run_reindex_job(self.job, state_store=store, archives=archives)

        self.assertNotIn("reset_index", archives.calls)


if __name__ == "__main__":
    unittest.main()
