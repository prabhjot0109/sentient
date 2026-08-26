"""The three S6 findings, closed: the zip-bomb cap, the key cap, and the crash.

Each was raised as its own item by the Phase S audit rather than folded into
SECURITY.md, on the grounds that a control nobody can test is a paragraph. This
is the test.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import httpx
from langchain_core.documents import Document

from sentient.adapters.state.postgres_store import PostgresStateStore, _is_uuid


class ExtractionCapTests(unittest.TestCase):
    """S2's one open sub-item. H6's cap counts bytes on the wire; this counts
    what those bytes turn into, which is what actually costs money."""

    def _archives(self, limit: int):
        from sentient.adapters.documents import ArchivesIngestion
        from sentient.core.config import load_rag_settings

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        settings = replace(load_rag_settings(), extract_max_chars=limit)
        with patch("sentient.adapters.documents.build_embeddings"):
            return ArchivesIngestion(
                data_dir=tmp.name,
                index_path=str(Path(tmp.name) / "index"),
                settings=settings,
            )

    def test_text_within_the_limit_passes(self):
        archives = self._archives(1000)
        archives._assert_extraction_bounded(Path("small.pdf"), [Document(page_content="x" * 999)])

    def test_text_over_the_limit_is_rejected(self):
        from sentient.core.errors import InvalidRequest

        archives = self._archives(1000)
        with self.assertRaises(InvalidRequest) as caught:
            archives._assert_extraction_bounded(
                Path("bomb.pdf"), [Document(page_content="x" * 1001)]
            )
        # The message names the file and both numbers: "it failed" is not enough
        # for a user to know whether to split the document or give up.
        self.assertIn("bomb.pdf", str(caught.exception))
        self.assertIn("1,001", str(caught.exception))

    def test_the_limit_is_the_SUM_across_pages(self):
        """A bomb is many ordinary-looking pages, not one enormous one.

        Checking per page would let a 10,000-page PDF of 1,000 characters each
        through while rejecting a single legitimate page of 1,001.
        """
        from sentient.core.errors import InvalidRequest

        archives = self._archives(1000)
        with self.assertRaises(InvalidRequest):
            archives._assert_extraction_bounded(
                Path("many.pdf"), [Document(page_content="x" * 400) for _ in range(3)]
            )

    def test_the_default_clears_any_upload_the_byte_cap_allows(self):
        """A fresh clone must behave like main.

        The worst legitimate case is a plain-text file at the byte cap, which is
        one character per byte. The default has to sit above that or this control
        would reject uploads that work today.
        """
        from sentient.core.config import load_rag_settings

        settings = load_rag_settings()
        self.assertGreater(settings.extract_max_chars, settings.upload_max_bytes)


class ApiKeyCapTests(unittest.IsolatedAsyncioTestCase):
    """S6's key-minting row: `POST /v1/keys` had no ceiling at all."""

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {"DATA_DIR": self.tmp.name, "MAX_API_KEYS_PER_USER": "3"})
        self.env.start()
        self.addCleanup(self.env.stop)

        from sentient.adapters.auth import IdentityCache
        from sentient.adapters.state import get_state_store
        from sentient.api import app as api
        from sentient.api import deps
        from sentient.core.config import load_rag_settings

        self.deps = deps
        deps._settings = load_rag_settings()
        deps.state_store = get_state_store(deps._settings)
        deps.identity_cache = IdentityCache()

        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://test"
        )
        self.addAsyncCleanup(self.client.aclose)

    async def _mint(self) -> httpx.Response:
        return await self.client.post("/v1/keys", json={"label": "probe"})

    async def test_minting_stops_at_the_cap(self):
        for index in range(3):
            self.assertEqual((await self._mint()).status_code, 200, f"key {index}")

        refused = await self._mint()
        self.assertEqual(refused.status_code, 409)
        self.assertIn("limit 3", refused.json()["detail"])

    async def test_revoking_makes_room(self):
        """Revoked rows must not count, or a user who cleaned up is wedged forever."""
        ids = [(await self._mint()).json()["id"] for _ in range(3)]
        self.assertEqual((await self._mint()).status_code, 409)

        revoked = await self.client.delete(f"/v1/keys/{ids[0]}")
        self.assertTrue(revoked.json()["revoked"])
        self.assertEqual((await self._mint()).status_code, 200)

    async def test_a_zero_cap_means_unlimited(self):
        with patch.object(
            self.deps, "_settings", replace(self.deps._settings, max_api_keys_per_user=0)
        ):
            for _ in range(8):
                self.assertEqual((await self._mint()).status_code, 200)


class MalformedIdIsNotACrashTests(unittest.IsolatedAsyncioTestCase):
    """F9's finding: `GET /v1/projects/does-not-exist` was a plain-text 500 on
    Postgres and a clean 404 on SQLite.

    asyncpg refuses to **bind** a non-UUID string to a `uuid` parameter -- a
    `DataError` raised before the query is even sent, so no route code ran and
    the response was Starlette's bare error page.

    Every guard runs before `_pool_()`, which is what lets these run with no
    database at all: the store is constructed against a DSN that resolves to
    nothing, and a single missed guard would hang or raise instead of answering.
    """

    def setUp(self):
        self.store = PostgresStateStore("postgresql://nobody@127.0.0.1:1/nowhere")

    def test_the_uuid_check_accepts_real_ids_and_rejects_the_rest(self):
        self.assertTrue(_is_uuid("9a2fcd39-a998-40c0-818e-e591f2a2900f"))
        # SQLite mints uuid4().hex -- no dashes -- and UUID() accepts that form,
        # which matters because both stores' ids flow through the same routers.
        self.assertTrue(_is_uuid("9a2fcd39a99840c0818ee591f2a2900f"))
        for bad in ("does-not-exist", "", "../etc/passwd", None, 42):
            self.assertFalse(_is_uuid(bad), bad)

    async def test_lookups_answer_not_found_instead_of_crashing(self):
        self.assertIsNone(await self.store.get_project("u", "does-not-exist"))
        self.assertIsNone(await self.store.get_project_config("does-not-exist"))
        self.assertIsNone(await self.store.get_thread("u", "does-not-exist"))
        self.assertIsNone(await self.store.rename_project("u", "does-not-exist", "n"))
        self.assertIsNone(await self.store.rename_thread("u", "does-not-exist", "t"))

    async def test_deletes_answer_false_instead_of_crashing(self):
        self.assertFalse(await self.store.delete_project("u", "does-not-exist"))
        self.assertFalse(await self.store.delete_thread("u", "does-not-exist"))
        self.assertFalse(await self.store.revoke_api_key("u", "does-not-exist"))

    async def test_listings_answer_empty_instead_of_crashing(self):
        self.assertEqual(await self.store.list_documents("does-not-exist"), [])
        self.assertEqual(await self.store.list_threads("does-not-exist"), [])
        self.assertEqual(await self.store.list_messages("does-not-exist"), [])


if __name__ == "__main__":
    unittest.main()
