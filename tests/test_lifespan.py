from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


class LifespanTests(unittest.IsolatedAsyncioTestCase):
    async def test_ingest_queue_stops_when_lifespan_body_fails(self):
        from sentient.api import app as api
        from sentient.api import deps

        queue = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
        with (
            patch.object(deps, "ingest_queue", queue),
            patch.object(deps, "any_provider_key_present", return_value=False),
            self.assertRaisesRegex(RuntimeError, "boom"),
        ):
            async with api.lifespan(api.app):
                queue.start.assert_awaited_once()
                raise RuntimeError("boom")

        queue.stop.assert_awaited_once()

    async def test_lifespan_warms_the_grounding_path_with_a_real_query(self):
        from sentient.api import app as api
        from sentient.api import deps

        archives = SimpleNamespace(
            ensure_index=AsyncMock(),
            retrieve=AsyncMock(return_value=[]),
        )
        queue = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
        with (
            patch.object(deps, "ingest_queue", queue),
            patch.object(
                deps, "reindex_queue", SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
            ),
            patch.object(deps, "any_provider_key_present", return_value=True),
            patch.object(deps, "get_default_archives", return_value=archives),
        ):
            async with api.lifespan(api.app):
                pass

        # A real embedding pass, not just an index build: the torch graph and the
        # ~9s model load are only paid by an actual query.
        archives.retrieve.assert_awaited_once()

    async def test_warmup_failure_never_stops_startup(self):
        from sentient.api import app as api
        from sentient.api import deps

        archives = SimpleNamespace(
            ensure_index=AsyncMock(),
            retrieve=AsyncMock(side_effect=RuntimeError("no index yet")),
        )
        queue = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
        with (
            patch.object(deps, "ingest_queue", queue),
            patch.object(
                deps, "reindex_queue", SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
            ),
            patch.object(deps, "any_provider_key_present", return_value=True),
            patch.object(deps, "get_default_archives", return_value=archives),
        ):
            async with api.lifespan(api.app):
                pass  # must not raise

        queue.stop.assert_awaited_once()

    async def test_warmup_is_skipped_without_a_provider_key(self):
        from sentient.api import app as api
        from sentient.api import deps

        archives = SimpleNamespace(ensure_index=AsyncMock(), retrieve=AsyncMock())
        queue = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
        with (
            patch.object(deps, "ingest_queue", queue),
            patch.object(
                deps, "reindex_queue", SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
            ),
            patch.object(deps, "any_provider_key_present", return_value=False),
            patch.object(deps, "get_default_archives", return_value=archives),
        ):
            async with api.lifespan(api.app):
                pass

        # Nothing to warm without a key: clients are built per-request, and a real
        # retrieval here would load an embedding model no request will use.
        archives.retrieve.assert_not_awaited()


class StuckIngestReconciliationAtStartupTests(unittest.IsolatedAsyncioTestCase):
    """H7. A restart mid-ingest leaves documents.status='processing' with no job
    to finish it, and F6 would render that as an in-flight ingest forever."""

    def _queues(self):
        return SimpleNamespace(start=AsyncMock(), stop=AsyncMock())

    async def test_startup_fails_rows_left_in_flight_by_the_previous_process(self):
        import tempfile
        from pathlib import Path

        from sentient.adapters.state.sqlite_store import SQLiteStateStore
        from sentient.api import app as api
        from sentient.api import deps

        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStateStore(str(Path(tmp) / "state.db"))
            user = await store.ensure_user("lifespan-owner")
            project = await store.create_project(user["id"], "Skyrim")
            await store.register_document(project["id"], "a.pdf", 0, "sig", status="processing")
            await store.register_document(project["id"], "b.pdf", 3, "sig", status="ready")

            with (
                patch.object(deps, "ingest_queue", self._queues()),
                patch.object(deps, "reindex_queue", self._queues()),
                patch.object(deps, "any_provider_key_present", return_value=False),
                patch.object(deps, "state_store", store),
            ):
                async with api.lifespan(api.app):
                    pass

            documents = await store.list_documents(project["id"])

        self.assertEqual(
            {d["filename"]: d["status"] for d in documents},
            {"a.pdf": "failed", "b.pdf": "ready"},
        )

    async def test_a_reconciliation_failure_never_stops_startup(self):
        from sentient.api import app as api
        from sentient.api import deps

        store = SimpleNamespace(
            fail_stuck_documents=AsyncMock(side_effect=RuntimeError("database is locked"))
        )
        queue = self._queues()
        with (
            patch.object(deps, "ingest_queue", queue),
            patch.object(deps, "reindex_queue", self._queues()),
            patch.object(deps, "any_provider_key_present", return_value=False),
            patch.object(deps, "state_store", store),
        ):
            async with api.lifespan(api.app):
                pass  # must not raise

        queue.stop.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
