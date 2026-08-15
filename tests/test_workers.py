from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sentient.api.routers import completions as completions_router


class IngestQueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_processes_jobs_and_reports_done(self):
        from sentient.core.concurrency import IngestJob, IngestQueue

        processed = []

        async def handler(job):
            processed.append(job.filename)

        queue = IngestQueue(handler)
        await queue.start()
        await queue.enqueue(IngestJob("p", "uk", None, "/x/a.pdf", "a.pdf", "sig"))
        await queue.stop()

        self.assertEqual(processed, ["a.pdf"])

    async def test_handler_error_does_not_kill_worker(self):
        from sentient.core.concurrency import IngestJob, IngestQueue

        seen = []

        async def handler(job):
            if job.filename == "bad":
                raise RuntimeError("boom")
            seen.append(job.filename)

        queue = IngestQueue(handler)
        await queue.start()
        await queue.enqueue(IngestJob("p", "uk", None, "/x", "bad", "s"))
        await queue.enqueue(IngestJob("p", "uk", None, "/x", "good", "s"))
        await queue.stop()

        self.assertEqual(seen, ["good"])

    async def test_stop_drains_accepted_jobs_in_fifo_order(self):
        from sentient.core.concurrency import IngestJob, IngestQueue

        started = asyncio.Event()
        release = asyncio.Event()
        order = []

        async def handler(job):
            order.append(f"{job.filename}-start")
            if job.filename == "first":
                started.set()
                await release.wait()
            order.append(f"{job.filename}-end")

        queue = IngestQueue(handler)
        await queue.start()
        await queue.enqueue(IngestJob("p", "uk", None, "/1", "first", "s"))
        await queue.enqueue(IngestJob("p", "uk", None, "/2", "second", "s"))
        await started.wait()

        stopping = asyncio.create_task(queue.stop())
        await asyncio.sleep(0)
        self.assertFalse(stopping.done())
        release.set()
        await stopping

        self.assertEqual(
            order,
            ["first-start", "first-end", "second-start", "second-end"],
        )
        await asyncio.wait_for(queue._queue.join(), timeout=0.1)
        await queue.stop()


class IngestHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_ingest_handler_awaits_add_and_marks_project_ready(self):
        from sentient.api import deps
        from sentient.core.concurrency import IngestJob

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lore.txt"
            path.write_text("lore", encoding="utf-8")
            archives = SimpleNamespace(
                data_dir=Path(tmp),
                add_file=AsyncMock(return_value={"added_chunk_count": 3}),
            )
            store = SimpleNamespace(
                register_document=AsyncMock(),
                set_document_status=AsyncMock(),
            )
            job = IngestJob("project-a", "tenant-a", None, str(path), "lore.txt", "sig-a", archives)

            with patch.object(deps, "state_store", store):
                await deps._ingest_handler(job)

        archives.add_file.assert_awaited_once_with(
            str(path),
            user_key="tenant-a",
            project_id="project-a",
            embedding_signature="sig-a",
        )
        store.register_document.assert_awaited_once_with(
            "project-a", "lore.txt", 3, "sig-a", status="ready"
        )
        store.set_document_status.assert_not_awaited()

    async def test_ingest_handler_marks_project_failed(self):
        from sentient.api import deps
        from sentient.core.concurrency import IngestJob

        archives = SimpleNamespace(
            data_dir=Path("/tmp"),
            add_file=AsyncMock(side_effect=RuntimeError("embed failed")),
        )
        store = SimpleNamespace(
            register_document=AsyncMock(),
            set_document_status=AsyncMock(),
        )
        job = IngestJob(
            "project-a", "tenant-a", None, "/tmp/lore.txt", "lore.txt", "sig-a", archives
        )

        with (
            patch.object(deps, "state_store", store),
            self.assertRaisesRegex(RuntimeError, "embed failed"),
        ):
            await deps._ingest_handler(job)

        store.set_document_status.assert_awaited_once_with("project-a", "lore.txt", "failed")


class SessionLockTests(unittest.IsolatedAsyncioTestCase):
    async def test_mutations_for_a_session_serialize(self):
        from sentient.core.concurrency import SessionLocks

        locks = SessionLocks()
        order = []

        async def mutate(tag, delay):
            async with locks.lock("sess-1"):
                order.append(f"{tag}-start")
                await asyncio.sleep(delay)
                order.append(f"{tag}-end")

        await asyncio.gather(mutate("A", 0.02), mutate("B", 0.0))

        self.assertEqual(order, ["A-start", "A-end", "B-start", "B-end"])


class DeferredTurnTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_schedules_session_work_after_completion(self):

        class _LLM:
            async def astream(self, messages):
                yield SimpleNamespace(content="Done.")

        ctx = SimpleNamespace()
        with patch.object(completions_router, "_schedule_deferred_turn_work") as schedule:
            events = [
                event
                async for event in completions_router._stream_with_deferred_turn_work(
                    _LLM(), [], "test-model", ctx
                )
            ]

        self.assertTrue(events[-1].endswith("[DONE]\n\n"))
        schedule.assert_called_once_with(ctx)


class SessionLockEvictionTests(unittest.IsolatedAsyncioTestCase):
    async def test_lock_table_is_bounded(self):
        from sentient.core.concurrency import SessionLocks

        locks = SessionLocks(maxsize=8)
        for i in range(100):
            locks.lock(f"session-{i}")

        self.assertLessEqual(len(locks._locks), 8)

    async def test_a_held_lock_is_never_evicted(self):
        from sentient.core.concurrency import SessionLocks

        locks = SessionLocks(maxsize=4)
        held = locks.lock("busy")
        await held.acquire()
        try:
            for i in range(50):
                locks.lock(f"session-{i}")
            # Same object => the in-flight critical section still excludes others.
            self.assertIs(locks.lock("busy"), held)
        finally:
            held.release()

    async def test_the_same_session_keeps_the_same_lock(self):
        from sentient.core.concurrency import SessionLocks

        locks = SessionLocks(maxsize=64)
        self.assertIs(locks.lock("sess-1"), locks.lock("sess-1"))

    async def test_growing_past_maxsize_beats_breaking_mutual_exclusion(self):
        from sentient.core.concurrency import SessionLocks

        locks = SessionLocks(maxsize=3)
        held = [locks.lock(f"busy-{i}") for i in range(3)]
        for lock in held:
            await lock.acquire()
        try:
            # Every entry is in use, so the table has to grow rather than hand a
            # fresh lock to a session that is mid-write.
            fresh = locks.lock("newcomer")
            self.assertGreater(len(locks._locks), 3)
            for i, lock in enumerate(held):
                self.assertIs(locks.lock(f"busy-{i}"), lock)
            self.assertIsNot(fresh, held[0])
        finally:
            for lock in held:
                lock.release()

    async def test_recently_used_locks_survive_eviction(self):
        from sentient.core.concurrency import SessionLocks

        locks = SessionLocks(maxsize=4)
        keep = locks.lock("keep-me")
        for i in range(20):
            locks.lock(f"filler-{i}")
            locks.lock("keep-me")  # touch it so LRU order favours it

        self.assertIs(locks.lock("keep-me"), keep)


if __name__ == "__main__":
    unittest.main()
