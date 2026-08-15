from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


class LifespanTests(unittest.IsolatedAsyncioTestCase):
    async def test_ingest_queue_stops_when_lifespan_body_fails(self):
        from sentient.api import app as api

        queue = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
        with (
            patch.object(api, "ingest_queue", queue),
            patch.object(api, "any_provider_key_present", return_value=False),
        ):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                async with api.lifespan(api.app):
                    queue.start.assert_awaited_once()
                    raise RuntimeError("boom")

        queue.stop.assert_awaited_once()

    async def test_lifespan_warms_the_grounding_path_with_a_real_query(self):
        from sentient.api import app as api

        archives = SimpleNamespace(
            ensure_index=AsyncMock(),
            retrieve=AsyncMock(return_value=[]),
        )
        queue = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
        with (
            patch.object(api, "ingest_queue", queue),
            patch.object(api, "reindex_queue", SimpleNamespace(start=AsyncMock(), stop=AsyncMock())),
            patch.object(api, "any_provider_key_present", return_value=True),
            patch.object(api, "get_default_archives", return_value=archives),
        ):
            async with api.lifespan(api.app):
                pass

        # A real embedding pass, not just an index build: the torch graph and the
        # ~9s model load are only paid by an actual query.
        archives.retrieve.assert_awaited_once()

    async def test_warmup_failure_never_stops_startup(self):
        from sentient.api import app as api

        archives = SimpleNamespace(
            ensure_index=AsyncMock(),
            retrieve=AsyncMock(side_effect=RuntimeError("no index yet")),
        )
        queue = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
        with (
            patch.object(api, "ingest_queue", queue),
            patch.object(api, "reindex_queue", SimpleNamespace(start=AsyncMock(), stop=AsyncMock())),
            patch.object(api, "any_provider_key_present", return_value=True),
            patch.object(api, "get_default_archives", return_value=archives),
        ):
            async with api.lifespan(api.app):
                pass  # must not raise

        queue.stop.assert_awaited_once()

    async def test_warmup_is_skipped_without_a_provider_key(self):
        from sentient.api import app as api

        archives = SimpleNamespace(ensure_index=AsyncMock(), retrieve=AsyncMock())
        queue = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
        with (
            patch.object(api, "ingest_queue", queue),
            patch.object(api, "reindex_queue", SimpleNamespace(start=AsyncMock(), stop=AsyncMock())),
            patch.object(api, "any_provider_key_present", return_value=False),
            patch.object(api, "get_default_archives", return_value=archives),
        ):
            async with api.lifespan(api.app):
                pass

        # Nothing to warm without a key: clients are built per-request, and a real
        # retrieval here would load an embedding model no request will use.
        archives.retrieve.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
