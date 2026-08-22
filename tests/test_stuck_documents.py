from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sentient.adapters.state.sqlite_store import SQLiteStateStore


class StuckDocumentReconciliationTests(unittest.IsolatedAsyncioTestCase):
    """The queue is in-process and not crash-durable. Anything left mid-flight
    when the process died is not going to finish on its own."""

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteStateStore(str(Path(self.tmp.name) / "state.db"))
        user = await self.store.ensure_user("stuck-owner")
        self.project = await self.store.create_project(user["id"], "Skyrim")

    async def _register(self, filename: str, status: str):
        await self.store.register_document(self.project["id"], filename, 0, "sig", status=status)

    async def test_orphaned_rows_are_marked_failed(self):
        await self._register("a.pdf", "processing")
        await self._register("b.pdf", "ready")
        await self._register("c.pdf", "reindexing")

        self.assertEqual(await self.store.fail_stuck_documents(), 2)

        documents = await self.store.list_documents(self.project["id"])
        self.assertEqual(
            {d["filename"]: d["status"] for d in documents},
            {"a.pdf": "failed", "b.pdf": "ready", "c.pdf": "failed"},
        )

    async def test_it_is_idempotent(self):
        await self._register("a.pdf", "processing")
        self.assertEqual(await self.store.fail_stuck_documents(), 1)
        self.assertEqual(await self.store.fail_stuck_documents(), 0)

    async def test_a_clean_database_reports_nothing_changed(self):
        self.assertEqual(await self.store.fail_stuck_documents(), 0)

    async def test_an_already_failed_row_is_left_alone(self):
        """Only in-flight states are reconciled; `failed` is already the truth."""
        await self._register("a.pdf", "failed")
        self.assertEqual(await self.store.fail_stuck_documents(), 0)

    async def test_it_spans_every_project_and_every_user(self):
        """Startup reconciliation is process-wide: the dead process could have
        been mid-ingest for any tenant."""
        stranger = await self.store.ensure_user("stuck-stranger")
        theirs = await self.store.create_project(stranger["id"], "Fallout")
        await self._register("a.pdf", "processing")
        await self.store.register_document(theirs["id"], "b.pdf", 0, "sig", status="processing")

        self.assertEqual(await self.store.fail_stuck_documents(), 2)


if __name__ == "__main__":
    unittest.main()
