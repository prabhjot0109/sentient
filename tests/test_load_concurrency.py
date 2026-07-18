from __future__ import annotations

import asyncio
import os
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

import httpx


class LoadConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"DATA_DIR": self.tmp.name}, clear=False)
        self.env.start()
        for name in ("DATABASE_URL", "NEON_AUTH_JWKS_URL"):
            os.environ.pop(name, None)

        import api
        from logic.auth import IdentityCache
        from logic.config import load_rag_settings
        from logic.registry import ObjectRegistry
        from logic.runtime import RuntimeCache
        from logic.state import get_state_store

        self.api = api
        api._settings = load_rag_settings()
        api.state_store = get_state_store(api._settings)
        api.identity_cache = IdentityCache()
        api.runtime_cache = RuntimeCache()
        api.object_registry = ObjectRegistry()

    async def asyncTearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()

    async def test_concurrent_tenants_interleave(self) -> None:
        from logic.auth import hash_key

        owner = await self.api.state_store.ensure_user("load-test-owner")
        keys = [f"sk-sent-load-{index}" for index in range(10)]
        for key in keys:
            await self.api.state_store.create_api_key(owner["id"], hash_key(key))

        class _SlowLLM:
            async def ainvoke(self, messages):
                await asyncio.sleep(0.05)

                class _Response:
                    content = "ok"

                return _Response()

        class _StubArchives:
            async def retrieve(self, *args, **kwargs):
                return []

        with (
            patch.object(
                self.api,
                "build_llm",
                new_callable=AsyncMock,
                return_value=_SlowLLM(),
            ),
            patch.object(
                self.api,
                "get_archives_for_context",
                new_callable=AsyncMock,
                return_value=_StubArchives(),
            ),
        ):
            transport = httpx.ASGITransport(app=self.api.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                async def one(key: str):
                    return await client.post(
                        f"/v1/{key}/chat/completions",
                        json={"messages": [{"role": "user", "content": "hi"}]},
                    )

                started = time.perf_counter()
                responses = await asyncio.gather(*(one(key) for key in keys))
                elapsed = time.perf_counter() - started

        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertLess(elapsed, 0.25)


if __name__ == "__main__":
    unittest.main()
