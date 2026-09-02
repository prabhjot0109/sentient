"""A failed rebuild has to be distinguishable from a queued one.

`projects.status = 'reindexing_required'` carries two meanings — "a rebuild is
queued" (`update_config`) and "a rebuild failed" (`run_reindex_job`'s except) —
and nothing could tell them apart. A guard that tried 409'd a failed project
forever, which `478e591` fixed by deleting the guard rather than the ambiguity.
The user-visible consequence survived: the console shows a project that is about
to be fine, forever.

The fix is a *reason* attached to a known state, not a second state. `projects`
already has `status`; documents already carry `error` the same way. A distinct
`reindex_failed` status would grow a case in every consumer that switches on
`status`, and would still need to accept a retry that put it back to
`reindexing_required` — two states where one plus a reason does the job.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from sentient.adapters.state.sqlite_store import SQLiteStateStore
from sentient.core.concurrency import ReindexJob
from sentient.core.errors import SourceFilesMissing
from sentient.services.ingestion import run_reindex_job


class ReindexErrorColumnTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteStateStore(str(Path(self.tmp.name) / "state.db"))
        self.user = await self.store.ensure_user("reindex-owner")
        self.project = await self.store.create_project(self.user["id"], "Skyrim")

    async def _reindex_error(self) -> str | None:
        project = await self.store.get_project(self.user["id"], self.project["id"])
        return project["reindex_error"]

    async def test_a_new_project_has_no_reason(self):
        """Present and null, not absent. A key the console has to test for with
        `in` rather than read is a shape divergence waiting to happen."""
        self.assertIn("reindex_error", self.project)
        self.assertIsNone(self.project["reindex_error"])
        self.assertIsNone(await self._reindex_error())

    async def test_it_round_trips(self):
        await self.store.set_reindex_error(self.project["id"], "the provider refused: 429")
        self.assertEqual(await self._reindex_error(), "the provider refused: 429")

    async def test_it_can_be_cleared(self):
        await self.store.set_reindex_error(self.project["id"], "boom")
        await self.store.set_reindex_error(self.project["id"], None)
        self.assertIsNone(await self._reindex_error())

    async def test_it_reaches_the_project_listing(self):
        """The sidebar is where a user notices a project is unwell, so the reason
        cannot be detail-only."""
        await self.store.set_reindex_error(self.project["id"], "boom")
        listed = await self.store.list_projects(self.user["id"])
        self.assertEqual(listed[0]["reindex_error"], "boom")

    async def test_it_reaches_the_project_detail_response(self):
        from sentient.services.projects import get_project_detail

        await self.store.set_reindex_error(self.project["id"], "boom")
        detail = await get_project_detail(
            self.store, user_id=self.user["id"], project_id=self.project["id"]
        )
        self.assertEqual(detail["reindex_error"], "boom")


class ReindexJobWritesTheReasonTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data_dir = Path(self.tmp.name) / "data"
        self.data_dir.mkdir()
        self.store = SQLiteStateStore(str(Path(self.tmp.name) / "state.db"))
        self.user = await self.store.ensure_user("reindex-owner")
        self.project = await self.store.create_project(self.user["id"], "Skyrim")
        self.job = ReindexJob(
            project_id=self.project["id"],
            user_key="user-key",
            api_key=None,
            embedding_signature="sig-2",
            user_id=self.user["id"],
        )

    def _archives(self, *, add_file=None):
        archives = Mock()
        archives.data_dir = self.data_dir
        archives.settings = Mock(vector_backend="qdrant")
        archives.clear_project = Mock()
        archives.reset_index = Mock()
        archives.add_file = add_file or AsyncMock(return_value={"added_chunk_count": 3})
        return archives

    async def _reindex_error(self) -> str | None:
        project = await self.store.get_project(self.user["id"], self.project["id"])
        return project["reindex_error"]

    async def _register(self, filename: str, *, on_disk: bool = True):
        if on_disk:
            (self.data_dir / filename).write_text("lore", encoding="utf-8")
        await self.store.register_document(self.project["id"], filename, 1, "sig-1", status="ready")

    async def test_a_provider_failure_is_recorded_as_words(self):
        """The traceback lives in the server log, which the user cannot read. The
        column carries the one sentence they can act on."""
        await self._register("a.pdf")
        archives = self._archives(add_file=AsyncMock(side_effect=RuntimeError("rate limited: 429")))

        with self.assertRaises(RuntimeError):
            await run_reindex_job(self.job, state_store=self.store, archives=archives)

        reason = await self._reindex_error()
        assert reason is not None
        self.assertIn("rate limited: 429", reason)

    async def test_missing_source_files_record_the_sentence_the_user_needs(self):
        """The refusal already writes a human sentence naming the files and the
        cause. Passing it through beats covering it with generic copy."""
        await self._register("gone.pdf", on_disk=False)

        with self.assertRaises(SourceFilesMissing):
            await run_reindex_job(self.job, state_store=self.store, archives=self._archives())

        reason = await self._reindex_error()
        assert reason is not None
        self.assertIn("gone.pdf", reason)
        self.assertIn("Re-upload", reason)

    async def test_success_clears_a_stale_reason(self):
        """Cleared in the success path, not only on the next failure. A project
        that recovers must not keep explaining a problem it no longer has."""
        await self._register("a.pdf")
        await self.store.set_reindex_error(self.project["id"], "a problem from last time")

        await run_reindex_job(self.job, state_store=self.store, archives=self._archives())

        self.assertIsNone(await self._reindex_error())
        project = await self.store.get_project(self.user["id"], self.project["id"])
        self.assertEqual(project["status"], "active")

    async def test_the_status_still_says_a_rebuild_is_wanted(self):
        """The reason is a diagnosis attached to a known state, not a new state.
        Nothing that switches on `status` grows a case, and a retry is still the
        ordinary path back."""
        await self._register("a.pdf")
        archives = self._archives(add_file=AsyncMock(side_effect=RuntimeError("boom")))

        with self.assertRaises(RuntimeError):
            await run_reindex_job(self.job, state_store=self.store, archives=archives)

        project = await self.store.get_project(self.user["id"], self.project["id"])
        self.assertEqual(project["status"], "reindexing_required")


if __name__ == "__main__":
    unittest.main()
