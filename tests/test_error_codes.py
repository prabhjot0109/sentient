"""`X-Error-Code` — the header that tells two 409s apart.

409 is answered both by the reindex guard and by the API-key cap, and the two
lead to opposite next actions. Before this header a client could only see the
status, so the console rendered "your lore is re-embedding" at a user who had
simply run out of key slots.
"""

from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sentient.api import deps
from sentient.api.app import configure_middleware
from sentient.api.responses import ERROR_CODE_HEADER, error_headers
from sentient.api.routers import keys
from sentient.core.errors import NotFound, ReindexInProgress, SentientError


class ErrorCodeTests(unittest.TestCase):
    def test_every_domain_error_carries_a_distinct_code(self):
        codes = [cls.code for cls in SentientError.__subclasses__()]
        self.assertEqual(len(codes), len(set(codes)), "two domain errors share a code")
        self.assertNotIn(SentientError.code, codes, "a subclass never inherits the base code")

    def test_error_headers_reads_the_code_off_an_instance(self):
        self.assertEqual(
            error_headers(ReindexInProgress("rebuilding")),
            {ERROR_CODE_HEADER: "reindex_in_progress"},
        )
        self.assertEqual(error_headers(NotFound("nope")), {ERROR_CODE_HEADER: "not_found"})

    def test_error_headers_accepts_a_bare_string_for_routes_with_no_domain_type(self):
        self.assertEqual(error_headers("api_key_limit"), {ERROR_CODE_HEADER: "api_key_limit"})


class KeyLimitHeaderTests(unittest.IsolatedAsyncioTestCase):
    """The one 409 that is NOT a reindex, driven through the real route."""

    async def test_the_cap_answers_409_with_the_api_key_limit_code(self):
        app = FastAPI()
        app.include_router(keys.router)

        class Store:
            async def list_api_keys(self, user_id):
                return [{"id": str(n), "revoked": False} for n in range(2)]

        # `RAGSettings` is a FROZEN dataclass, so the field cannot be patched in
        # place -- the whole object is swapped for a copy carrying the one change.
        with (
            patch.object(deps, "state_store", Store()),
            patch.object(deps, "_settings", replace(deps._settings, max_api_keys_per_user=2)),
        ):
            app.dependency_overrides[deps.current_user] = lambda: ("user-1", "key-1")
            client = TestClient(app)
            response = client.post("/v1/keys", json={"label": "third"})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.headers[ERROR_CODE_HEADER], "api_key_limit")
        # The body is unchanged, so a client that ignores the header is unaffected.
        self.assertIn("revoke one", response.json()["detail"])

    async def test_revoked_keys_do_not_count_towards_the_cap(self):
        app = FastAPI()
        app.include_router(keys.router)

        class Store:
            async def list_api_keys(self, user_id):
                return [{"id": "a", "revoked": True}, {"id": "b", "revoked": True}]

            async def create_api_key(self, user_id, key_hash, label=None):
                return {"id": "new"}

        with (
            patch.object(deps, "state_store", Store()),
            patch.object(deps, "_settings", replace(deps._settings, max_api_keys_per_user=2)),
        ):
            app.dependency_overrides[deps.current_user] = lambda: ("user-1", "key-1")
            client = TestClient(app)
            response = client.post("/v1/keys", json={"label": "replacement"})

        self.assertEqual(response.status_code, 200)


class CorsExposureTests(unittest.TestCase):
    def test_the_header_is_exposed_or_a_browser_cannot_read_it(self):
        """`allow_headers` governs REQUESTS. Without this a browser sees nothing."""
        app = FastAPI()
        configure_middleware(app, deps._settings)

        cors = next(m for m in app.user_middleware if "CORS" in str(m.cls))
        self.assertIn(ERROR_CODE_HEADER, cors.kwargs["expose_headers"])


if __name__ == "__main__":
    unittest.main()
