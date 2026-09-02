from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sentient.adapters.state.sqlite_store import SQLiteStateStore


class StuckDocumentReconciliationTests(unittest.IsolatedAsyncioTestCase):
    """The queue is in-process and not crash-durable. Anything left mid-flight
    when the process died is not going to finish on its own.

    Two in-flight statuses, and they need opposite answers. `processing` means an
    upload that never completed, so the file may not even be in the archive and
    `failed` is the truth. `reindexing` means a document that was **already
    `ready`** when a rebuild started: the file is still on disk and the row is not
    failed, it is merely un-rebuilt. Marking it `failed` would tell the user to
    re-upload a file the system still has.
    """

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteStateStore(str(Path(self.tmp.name) / "state.db"))
        user = await self.store.ensure_user("stuck-owner")
        self.project = await self.store.create_project(user["id"], "Skyrim")

    async def _register(self, filename: str, status: str):
        await self.store.register_document(self.project["id"], filename, 0, "sig", status=status)

    async def _statuses(self, project_id: str | None = None):
        documents = await self.store.list_documents(project_id or self.project["id"])
        return {d["filename"]: d["status"] for d in documents}

    # ---- processing: an upload that never finished -------------------------

    async def test_orphaned_ingest_rows_are_marked_failed(self):
        await self._register("a.pdf", "processing")
        await self._register("b.pdf", "ready")

        self.assertEqual(await self.store.fail_stuck_documents(), 1)
        self.assertEqual(await self._statuses(), {"a.pdf": "failed", "b.pdf": "ready"})

    async def test_it_is_idempotent(self):
        await self._register("a.pdf", "processing")
        self.assertEqual(await self.store.fail_stuck_documents(), 1)
        self.assertEqual(await self.store.fail_stuck_documents(), 0)

    async def test_a_clean_database_reports_nothing_changed(self):
        self.assertEqual(await self.store.fail_stuck_documents(), 0)
        self.assertEqual(await self.store.restore_reindexing_documents(), [])

    async def test_an_already_failed_row_is_left_alone(self):
        """Only in-flight states are reconciled; `failed` is already the truth."""
        await self._register("a.pdf", "failed")
        self.assertEqual(await self.store.fail_stuck_documents(), 0)

    async def test_failing_ingests_does_not_touch_a_reindexing_row(self):
        """The two reconciliations are separate operations with opposite answers,
        so neither may quietly do the other's work."""
        await self._register("c.pdf", "reindexing")
        self.assertEqual(await self.store.fail_stuck_documents(), 0)
        self.assertEqual(await self._statuses(), {"c.pdf": "reindexing"})

    async def test_it_spans_every_project_and_every_user(self):
        """Startup reconciliation is process-wide: the dead process could have
        been mid-ingest for any tenant."""
        stranger = await self.store.ensure_user("stuck-stranger")
        theirs = await self.store.create_project(stranger["id"], "Fallout")
        await self._register("a.pdf", "processing")
        await self.store.register_document(theirs["id"], "b.pdf", 0, "sig", status="processing")

        self.assertEqual(await self.store.fail_stuck_documents(), 2)

    # ---- reindexing: a rebuild that never finished --------------------------

    async def test_a_row_stranded_mid_reindex_goes_back_to_ready(self):
        """`ready`, not `failed`. The document is still uploaded and still on
        disk; only its vectors are stale. `failed` is the console's "re-upload
        this", which is the wrong instruction for a file the system still holds.
        """
        await self._register("a.pdf", "reindexing")
        await self._register("b.pdf", "ready")

        self.assertEqual(await self.store.restore_reindexing_documents(), [self.project["id"]])
        self.assertEqual(await self._statuses(), {"a.pdf": "ready", "b.pdf": "ready"})

    async def test_it_names_the_projects_so_the_caller_can_guard_them(self):
        """`run_reindex_job` purges the project's vectors BEFORE rebuilding, so a
        crash mid-rebuild leaves every row in that project describing an index
        that is partly gone -- including the rows it never reached, which still
        read `ready`. The rows alone cannot express that; the project's status
        can, and `reindexing_required` is exactly "a rebuild is wanted", a state
        the system already converges out of."""
        stranger = await self.store.ensure_user("stuck-stranger")
        theirs = await self.store.create_project(stranger["id"], "Fallout")
        await self._register("a.pdf", "reindexing")
        await self._register("b.pdf", "reindexing")
        await self.store.register_document(theirs["id"], "c.pdf", 0, "sig", status="reindexing")

        affected = await self.store.restore_reindexing_documents()

        self.assertEqual(sorted(affected), sorted([self.project["id"], theirs["id"]]))
        self.assertEqual(len(affected), len(set(affected)), "one entry per project, not per row")

    async def test_restoring_is_idempotent(self):
        await self._register("a.pdf", "reindexing")
        self.assertEqual(await self.store.restore_reindexing_documents(), [self.project["id"]])
        self.assertEqual(await self.store.restore_reindexing_documents(), [])

    async def test_restoring_does_not_touch_a_processing_row(self):
        await self._register("a.pdf", "processing")
        self.assertEqual(await self.store.restore_reindexing_documents(), [])
        self.assertEqual(await self._statuses(), {"a.pdf": "processing"})


class StartupReconciliationTests(unittest.IsolatedAsyncioTestCase):
    """The lifespan wiring, which is where the two halves are put back together.

    A `reindexing` row restored to `ready` without the project being guarded
    would be a project serving retrieval against vectors that were purged on the
    way to a rebuild that never happened.
    """

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteStateStore(str(Path(self.tmp.name) / "state.db"))
        self.user = await self.store.ensure_user("restart-owner")
        self.project = await self.store.create_project(self.user["id"], "Skyrim")

    async def test_the_project_is_left_wanting_a_rebuild(self):
        from sentient.services.ingestion import reconcile_interrupted_work

        await self.store.register_document(
            self.project["id"], "a.pdf", 0, "sig", status="reindexing"
        )
        await self.store.set_project_status(self.project["id"], "active")

        result = await reconcile_interrupted_work(self.store)

        self.assertEqual(result, {"failed_ingests": 0, "restored_reindexes": 1})
        project = await self.store.get_project(self.user["id"], self.project["id"])
        self.assertEqual(project["status"], "reindexing_required")
        documents = await self.store.list_documents(self.project["id"])
        self.assertEqual(documents[0]["status"], "ready")

    async def test_a_clean_restart_changes_nothing(self):
        from sentient.services.ingestion import reconcile_interrupted_work

        await self.store.register_document(self.project["id"], "a.pdf", 0, "sig", status="ready")

        result = await reconcile_interrupted_work(self.store)

        self.assertEqual(result, {"failed_ingests": 0, "restored_reindexes": 0})
        project = await self.store.get_project(self.user["id"], self.project["id"])
        self.assertEqual(project["status"], "active")


if __name__ == "__main__":
    unittest.main()
