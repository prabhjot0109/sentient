from __future__ import annotations

import logging
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sentient.core.concurrency import IngestJob
from sentient.services import ingestion


@dataclass
class FakeSettings:
    vector_backend: str = "qdrant"


class FakeArchives:
    def __init__(self, data_dir: Path, *, fail: bool = False) -> None:
        self.data_dir = data_dir
        self.settings = FakeSettings()
        self.fail = fail

    async def add_file(self, path: str, **kwargs: Any) -> dict[str, Any]:
        if self.fail:
            raise RuntimeError("the embedding provider refused the request")
        return {"added_chunk_count": 45}


class FakeStore:
    def __init__(self) -> None:
        self.status: dict[str, str] = {}

    async def register_document(self, project_id, filename, chunk_count, signature, status):
        self.status[filename] = status

    async def set_document_status(self, project_id: str, filename: str, status: str) -> None:
        self.status[filename] = status


class IngestObservabilityTests(unittest.IsolatedAsyncioTestCase):
    """An ingest that says nothing is an ingest nobody can distinguish from a hang.

    Measured on the deployed 0.15-CPU instance, 2026-09-01: a scanned 6-page PDF
    took 15m51s to ingest, and for all fifteen of those minutes the log carried
    nothing between the upload's 202 and the eventual `ready`. The `documents` row
    does not change either, because status is written once at the end. So a healthy
    pipeline doing expensive work looked exactly like a broken one, and the only
    way to tell them apart was to read CPU metrics off the platform.

    These tests pin the three lines that make the difference: it started, it
    finished and how long it took, or it failed and why.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data_dir = Path(self.tmp.name)
        self.file = self.data_dir / "lore.pdf"
        self.file.write_text("lore", encoding="utf-8")
        self.job = IngestJob(
            project_id="project-1",
            user_key="user-1",
            api_key=None,
            file_path=str(self.file),
            filename="lore.pdf",
            embedding_signature="google:models/embedding-001",
        )

    async def _run(self, *, fail: bool) -> tuple[list[logging.LogRecord], FakeStore]:
        store = FakeStore()
        archives = FakeArchives(self.data_dir, fail=fail)
        with self.assertLogs("sentient", level="INFO") as captured:
            if fail:
                with self.assertRaises(RuntimeError):
                    await ingestion.run_ingest_job(self.job, state_store=store, archives=archives)
            else:
                await ingestion.run_ingest_job(self.job, state_store=store, archives=archives)
        return captured.records, store

    async def test_it_announces_the_start(self):
        """Before the slow part, not after.

        A line emitted only on completion is worth nothing during the fifteen
        minutes when someone is wondering whether to wait or refresh.
        """
        records, _ = await self._run(fail=False)

        starts = [r for r in records if r.getMessage() == "ingest started"]
        self.assertEqual(len(starts), 1)
        self.assertEqual(starts[0].file, "lore.pdf")

    async def test_it_reports_the_chunk_count_and_the_duration(self):
        records, store = await self._run(fail=False)

        done = next(r for r in records if r.getMessage() == "ingest complete")
        self.assertEqual(done.chunks, 45)
        self.assertIsInstance(done.seconds, float)
        self.assertEqual(store.status["lore.pdf"], "ready")

    async def test_a_failure_is_logged_with_the_filename(self):
        """The queue's own handler logs a failure without knowing which file.

        `IngestQueue._run` catches and logs, but it labels the record from
        `getattr(job, "filename", ...)` on a generic job, and it cannot report how
        long the work ran before giving up. Logging here keeps both in scope.
        """
        records, store = await self._run(fail=True)

        failed = next(r for r in records if r.getMessage() == "ingest failed")
        self.assertEqual(failed.file, "lore.pdf")
        self.assertEqual(failed.levelno, logging.ERROR)
        self.assertIsNotNone(failed.exc_info)
        self.assertEqual(store.status["lore.pdf"], "failed")

    async def test_the_failure_path_still_reraises(self):
        """The log must not swallow the exception.

        `IngestQueue` relies on it propagating, and the row is only marked failed
        by the same except block.
        """
        store = FakeStore()
        archives = FakeArchives(self.data_dir, fail=True)

        with self.assertLogs("sentient", level="INFO"), self.assertRaises(RuntimeError):
            await ingestion.run_ingest_job(self.job, state_store=store, archives=archives)


if __name__ == "__main__":
    unittest.main()
