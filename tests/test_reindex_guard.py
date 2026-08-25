"""B5: a lore search during a reindex must say so, not report an empty index.

Measured 2026-08-23: POST /v1/retrieve returned 200 {"chunks":[]} while the
project's status was reindexing_required, because the guard lived only in the two
chat entry points and retrieve_endpoint called neither.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from unittest import mock

from sentient.core.errors import ReindexInProgress
from sentient.services.chat import assert_retrievable


@dataclass
class _Ctx:
    project_id: str | None
    status: str


class AssertRetrievableTests(unittest.TestCase):
    def test_raises_while_the_project_is_reindexing(self):
        with self.assertRaises(ReindexInProgress) as caught:
            assert_retrievable(_Ctx(project_id="p1", status="reindexing_required"))
        self.assertEqual(
            str(caught.exception),
            "project is reindexing; retrieval temporarily unavailable",
        )

    def test_allows_an_active_project(self):
        self.assertIsNone(assert_retrievable(_Ctx(project_id="p1", status="active")))

    def test_allows_a_context_with_no_project(self):
        # `status` is read off the project row, so a project-less context cannot
        # legitimately carry `reindexing_required`. The two pre-existing copies of
        # this check disagreed on whether to test project_id at all; unifying on
        # the stricter form is only behaviour-preserving if this holds.
        self.assertIsNone(assert_retrievable(_Ctx(project_id=None, status="reindexing_required")))


if __name__ == "__main__":
    unittest.main()


class ReindexCompletionInvalidatesCacheTests(unittest.IsolatedAsyncioTestCase):
    """B6: the 409 must end when the rebuild ends, not when the TTL does.

    Measured 2026-08-23: a one-chunk project rebuilt in ~2 s and /v1/retrieve kept
    answering 409 for ~60 s, because _reindex_handler flips the project to
    'active' without telling RuntimeCache. The three write paths in
    services/projects.py all invalidate; this one did not.
    """

    async def _run_handler(self, *, fails: bool) -> list[str]:
        from sentient.api import deps
        from sentient.core.concurrency import ReindexJob

        job = ReindexJob(
            api_key="probe-key",
            user_id="user-1",
            user_key="user-1",
            project_id="project-1",
            embedding_signature="sig-2",
        )
        invalidated: list[str] = []

        async def fake_run_reindex_job(_job, *, state_store, archives):
            if fails:
                raise RuntimeError("embedding provider is down")

        with (
            mock.patch.object(deps.runtime_cache, "invalidate", invalidated.append),
            mock.patch.object(deps.ingestion, "run_reindex_job", fake_run_reindex_job),
            mock.patch.object(deps, "resolve_runtime_context", mock.AsyncMock()),
            mock.patch.object(deps, "get_archives_for_context", mock.AsyncMock()),
        ):
            if fails:
                with self.assertRaises(RuntimeError):
                    await deps._reindex_handler(job)
            else:
                await deps._reindex_handler(job)
        return invalidated

    async def test_invalidates_the_project_after_a_successful_rebuild(self):
        self.assertEqual(await self._run_handler(fails=False), ["project-1"])

    async def test_invalidates_the_project_after_a_failed_rebuild(self):
        # The status goes back to reindexing_required, which is what the cache
        # already holds -- but the invalidation must not depend on that staying true.
        self.assertEqual(await self._run_handler(fails=True), ["project-1"])
