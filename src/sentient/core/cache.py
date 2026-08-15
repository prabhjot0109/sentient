from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from cachetools import TTLCache


class ObjectRegistry:
    """Caches heavy client bundles by config signature so they are built once per
    distinct configuration and reused — keeping instantiation off the request hot path.

    Single-flight is per signature: concurrent first-hits for the same signature share
    one build, while builds for different signatures proceed in parallel. Locks are
    keyed by (event loop, signature) because asyncio.Lock binds to the loop it was
    created on; the entry is dropped once its build settles.
    """

    def __init__(self, maxsize: int = 128, ttl: float = 1800) -> None:
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._locks: dict[tuple[int, str], asyncio.Lock] = {}

    async def get(self, signature: str, builder: Callable[[], Awaitable[Any]]) -> Any:
        hit = self._cache.get(signature)
        if hit is not None:
            return hit
        lock_key = (id(asyncio.get_running_loop()), signature)
        lock = self._locks.setdefault(lock_key, asyncio.Lock())
        try:
            async with lock:
                hit = self._cache.get(signature)
                if hit is not None:
                    return hit
                obj = await builder()
                self._cache[signature] = obj
                return obj
        finally:
            self._locks.pop(lock_key, None)

    def size(self) -> int:
        return len(self._cache)

    def clear(self) -> None:
        self._cache.clear()
