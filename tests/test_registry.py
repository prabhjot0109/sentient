from __future__ import annotations

import asyncio
import unittest


class ObjectRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_builds_once_per_signature(self):
        from logic.registry import ObjectRegistry
        reg = ObjectRegistry()
        calls = {"n": 0}
        async def builder():
            calls["n"] += 1
            return object()
        a = await reg.get("sig-1", builder)
        b = await reg.get("sig-1", builder)
        self.assertIs(a, b)
        self.assertEqual(calls["n"], 1)

    async def test_concurrent_first_hits_build_once(self):
        from logic.registry import ObjectRegistry
        reg = ObjectRegistry()
        calls = {"n": 0}
        async def builder():
            calls["n"] += 1
            await asyncio.sleep(0.01)
            return object()
        results = await asyncio.gather(*[reg.get("s", builder) for _ in range(8)])
        self.assertEqual(calls["n"], 1)
        self.assertEqual(len({id(r) for r in results}), 1)

    async def test_maxsize_bounds(self):
        from logic.registry import ObjectRegistry
        reg = ObjectRegistry(maxsize=2, ttl=100)
        async def b(): return object()
        await reg.get("a", b); await reg.get("b", b); await reg.get("c", b)
        self.assertLessEqual(reg.size(), 2)

    async def test_distinct_signatures_build_concurrently(self):
        from logic.registry import ObjectRegistry
        reg = ObjectRegistry()
        started = asyncio.Event()
        release = asyncio.Event()
        async def slow():
            started.set()
            await release.wait()
            return "slow"
        async def fast():
            return "fast"
        slow_task = asyncio.create_task(reg.get("slow-sig", slow))
        await started.wait()
        # a global single-flight lock would block this until `release` fires
        fast_result = await asyncio.wait_for(reg.get("fast-sig", fast), timeout=1)
        self.assertEqual(fast_result, "fast")
        release.set()
        self.assertEqual(await slow_task, "slow")


if __name__ == "__main__":
    unittest.main()
