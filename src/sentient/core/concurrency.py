from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sentient.core.logging import get_logger

log = get_logger(__name__)


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
        self._maxsize = maxsize
        self._queue: asyncio.Queue[Any | None] = asyncio.Queue(maxsize=maxsize)
        self._task: asyncio.Task[None] | None = None
        self._accepting = False

    async def start(self) -> None:
        if self._task is None:
            # A fresh queue per start, not the one built in __init__. asyncio.Queue
            # binds to the first event loop that touches it and never unbinds, and
            # these instances are module-level singletons in api/deps.py that
            # outlive any one loop. A second lifespan -- a uvicorn reload worker,
            # or the next test -- would otherwise inherit a queue welded to a dead
            # loop and its worker would die on the first get(). Nothing can be in
            # flight here: enqueue() refuses while _task is None.
            self._queue = asyncio.Queue(maxsize=self._maxsize)
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
                except Exception:
                    label = getattr(job, "filename", getattr(job, "project_id", "unknown"))
                    log.exception("ingest job failed", extra={"job": label})
            finally:
                self._queue.task_done()

    async def enqueue(self, job: Any) -> None:
        if self._task is None or not self._accepting:
            raise RuntimeError("ingest queue is not running")
        self._queue.put_nowait(job)

    def depth(self) -> int:
        """Jobs waiting, excluding the one in flight.

        Sync and non-blocking so the readiness route can report it without awaiting
        anything: a probe that can block is a probe that can hang the thing it is
        supposed to be watching. Reads 0 before `start()`, which is correct rather
        than incidental -- nothing can be queued before the worker exists.
        """
        return self._queue.qsize()

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
        except Exception:
            log.exception("deferred task failed", extra={"label": label})

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
