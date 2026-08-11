from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass(frozen=True)
class IngestJob:
    project_id: str | None
    user_key: str | None
    api_key: str | None
    file_path: str
    filename: str
    embedding_signature: str
    archives: Any | None = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class ReindexJob:
    project_id: str
    user_key: str | None
    api_key: str | None
    embedding_signature: str
    user_id: str | None = field(default=None, repr=False, compare=False)


class IngestQueue:
    """Bounded in-process ingest queue.

    Jobs accepted before shutdown are drained in FIFO order. The queue is not
    crash-durable; callers depend only on ``enqueue`` so a durable worker can
    replace it later without changing the HTTP layer.
    """

    def __init__(
        self,
        handler: Callable[[Any], Awaitable[None]],
        *,
        maxsize: int = 64,
    ) -> None:
        self._handler = handler
        self._queue: asyncio.Queue[Any | None] = asyncio.Queue(maxsize=maxsize)
        self._task: asyncio.Task[None] | None = None
        self._accepting = False

    async def start(self) -> None:
        if self._task is None:
            self._accepting = True
            self._task = asyncio.create_task(self._run(), name="sentient-ingest-worker")

    async def _run(self) -> None:
        while True:
            job = await self._queue.get()
            try:
                if job is None:
                    return
                try:
                    await self._handler(job)
                except Exception as exc:
                    label = getattr(job, "filename", getattr(job, "project_id", "unknown"))
                    print(f"[ingest] job {label} failed: {exc}")
            finally:
                self._queue.task_done()

    async def enqueue(self, job: Any) -> None:
        if self._task is None or not self._accepting:
            raise RuntimeError("ingest queue is not running")
        self._queue.put_nowait(job)

    async def stop(self) -> None:
        task = self._task
        if task is None:
            return
        self._accepting = False
        await self._queue.join()
        await self._queue.put(None)
        await task
        self._task = None


def defer(coro: Awaitable[Any], *, label: str = "task") -> None:
    """Schedule post-response work and report failures without surfacing them."""

    async def _wrap() -> None:
        try:
            await coro
        except Exception as exc:
            print(f"[deferred:{label}] failed: {exc}")

    asyncio.create_task(_wrap(), name=f"sentient-deferred-{label}")


class SessionLocks:
    """Per-session FIFO locks for background mutations only.

    Bounded: one lock per distinct session id would otherwise live for the process
    lifetime. Only *unlocked* entries are ever evicted — dropping a held lock would
    hand the next caller a fresh one and silently break mutual exclusion for the
    session that is mid-write.

    No internal synchronisation is needed: `lock` is sync and contains no await, so
    it runs to completion within one event-loop step and cannot interleave.
    """

    def __init__(self, maxsize: int = 1024) -> None:
        self._locks: OrderedDict[str, asyncio.Lock] = OrderedDict()
        self._maxsize = maxsize

    def lock(self, session_id: str) -> asyncio.Lock:
        existing = self._locks.get(session_id)
        if existing is not None:
            self._locks.move_to_end(session_id)
            return existing

        self._evict()
        lock = self._locks[session_id] = asyncio.Lock()
        return lock

    def _evict(self) -> None:
        while len(self._locks) >= self._maxsize:
            for key, lock in self._locks.items():
                if not lock.locked():
                    del self._locks[key]
                    break
            else:
                # Every lock is in use. Growing past maxsize is the safe failure:
                # correctness beats the bound.
                return
