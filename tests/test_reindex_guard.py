"""B5: a lore search during a reindex must say so, not report an empty index.

Measured 2026-08-23: POST /v1/retrieve returned 200 {"chunks":[]} while the
project's status was reindexing_required, because the guard lived only in the two
chat entry points and retrieve_endpoint called neither.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass

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
