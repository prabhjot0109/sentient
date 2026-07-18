from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


class LifespanTests(unittest.IsolatedAsyncioTestCase):
    async def test_ingest_queue_stops_when_lifespan_body_fails(self):
        import api

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


if __name__ == "__main__":
    unittest.main()
