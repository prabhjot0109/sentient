from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

import httpx
from langchain_core.embeddings import Embeddings

from sentient.core.errors import InvalidRequest
from sentient.services.ingestion import safe_filename, sniff_content_type

PDF_MAGIC = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"


class FakeEmbeddings(Embeddings):
    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 1.0, 0.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


class FilenameSanitisationTests(unittest.TestCase):
    """os.path.basename was the only guard, and on POSIX it does not strip a
    Windows-style path at all."""

    def test_a_plain_name_survives(self):
        self.assertEqual(safe_filename("skyrim-lore.pdf"), "skyrim-lore.pdf")

    def test_posix_traversal_is_stripped(self):
        self.assertEqual(safe_filename("../../etc/passwd.txt"), "passwd.txt")

    def test_windows_traversal_is_stripped(self):
        self.assertEqual(safe_filename(r"..\..\Windows\System32\evil.txt"), "evil.txt")

    def test_an_absolute_path_is_stripped(self):
        self.assertEqual(safe_filename("/var/lib/secrets/lore.pdf"), "lore.pdf")

    def test_a_nul_byte_is_rejected(self):
        with self.assertRaises(InvalidRequest):
            safe_filename("lore\x00.pdf")

    def test_a_name_that_sanitises_to_nothing_is_rejected(self):
        for raw in ("", "   ", "..", "../", ".", None):
            with self.assertRaises(InvalidRequest):
                safe_filename(raw)

    def test_an_unsupported_extension_is_rejected(self):
        with self.assertRaises(InvalidRequest):
            safe_filename("payload.exe")

    def test_a_double_extension_is_judged_on_the_last_one(self):
        self.assertEqual(safe_filename("lore.exe.txt"), "lore.exe.txt")
        with self.assertRaises(InvalidRequest):
            safe_filename("lore.txt.exe")


class ContentSniffingTests(unittest.TestCase):
    """The extension is a claim, not evidence."""

    def test_a_real_pdf_passes(self):
        self.assertEqual(sniff_content_type(PDF_MAGIC, ".pdf"), "application/pdf")

    def test_a_renamed_binary_claiming_to_be_a_pdf_is_rejected(self):
        with self.assertRaises(InvalidRequest):
            sniff_content_type(b"MZ\x90\x00\x03", ".pdf")

    def test_utf8_text_passes_as_txt(self):
        self.assertEqual(sniff_content_type(b"Dragons of Skyrim", ".txt"), "text/plain")

    def test_a_binary_claiming_to_be_txt_is_rejected(self):
        with self.assertRaises(InvalidRequest):
            sniff_content_type(b"\x00\x01\x02\x03\xff\xfe", ".txt")

    def test_a_pdf_renamed_to_txt_is_rejected(self):
        with self.assertRaises(InvalidRequest):
            sniff_content_type(PDF_MAGIC, ".txt")

    def test_a_multibyte_character_cut_at_the_sniff_boundary_still_passes(self):
        """The head is the first KiB, which lands mid-character often enough to
        matter. That is not evidence of binary."""
        head = ("é" * 512).encode()[:1023]
        self.assertEqual(sniff_content_type(head, ".txt"), "text/plain")


class UserStorageAccountingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from pathlib import Path

        from sentient.adapters.state.sqlite_store import SQLiteStateStore

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteStateStore(str(Path(self.tmp.name) / "state.db"))

    async def test_the_sum_spans_a_users_projects_and_excludes_other_users(self):
        owner = await self.store.ensure_user("quota-owner")
        stranger = await self.store.ensure_user("quota-stranger")
        skyrim = await self.store.create_project(owner["id"], "Skyrim")
        fallout = await self.store.create_project(owner["id"], "Fallout")
        theirs = await self.store.create_project(stranger["id"], "Theirs")

        await self.store.register_document(skyrim["id"], "a.pdf", 1, "sig", size_bytes=100)
        await self.store.register_document(fallout["id"], "b.pdf", 1, "sig", size_bytes=250)
        await self.store.register_document(theirs["id"], "c.pdf", 1, "sig", size_bytes=9999)

        self.assertEqual(await self.store.user_storage_bytes(owner["id"]), 350)
        self.assertEqual(await self.store.user_storage_bytes(stranger["id"]), 9999)

    async def test_a_user_with_nothing_stored_sums_to_zero(self):
        owner = await self.store.ensure_user("empty-owner")
        self.assertEqual(await self.store.user_storage_bytes(owner["id"]), 0)

    async def test_a_row_with_no_recorded_size_does_not_break_the_sum(self):
        """Rows predating the size column read back as NULL."""
        owner = await self.store.ensure_user("legacy-owner")
        project = await self.store.create_project(owner["id"], "P")
        await self.store.register_document(project["id"], "old.pdf", 1, "sig")
        await self.store.register_document(project["id"], "new.pdf", 1, "sig", size_bytes=64)

        self.assertEqual(await self.store.user_storage_bytes(owner["id"]), 64)


class UploadRouteRejectionTests(unittest.IsolatedAsyncioTestCase):
    """Every rejection above has to actually surface as a 400 on the route, not
    just hold as a unit."""

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(
            os.environ,
            {
                "DATA_DIR": self.tmp.name,
                "VECTOR_BACKEND": "faiss",
                "UPLOAD_MAX_BYTES": "2048",
                "UPLOAD_USER_QUOTA_BYTES": "4096",
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)

        embeddings = patch(
            "sentient.adapters.documents.build_embeddings", return_value=FakeEmbeddings()
        )
        embeddings.start()
        self.addCleanup(embeddings.stop)

        from sentient.adapters.auth import IdentityCache
        from sentient.adapters.state import get_state_store
        from sentient.api import app as api
        from sentient.api import deps
        from sentient.core.cache import ObjectRegistry
        from sentient.core.config import load_rag_settings
        from sentient.services.runtime import RuntimeCache

        self.api = api
        self.deps = deps
        deps._settings = load_rag_settings()
        deps.state_store = get_state_store(deps._settings)
        deps.identity_cache = IdentityCache()
        deps.runtime_cache = RuntimeCache()
        deps.object_registry = ObjectRegistry()
        deps.get_default_archives.cache_clear()
        self.addCleanup(deps.get_default_archives.cache_clear)

        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://test"
        )
        self.addAsyncCleanup(self.client.aclose)

        # ASGITransport does not run the app lifespan, so the queue the 202 path
        # enqueues onto would still be stopped and every accepted upload would
        # answer 503. A *fresh* queue, not the module singleton: asyncio.Queue
        # binds to the first event loop that touches it, and IsolatedAsyncioTestCase
        # builds a new loop per test, so reusing it makes the second test's worker
        # die on "bound to a different event loop".
        from sentient.core.concurrency import IngestQueue

        original_queue = deps.ingest_queue
        deps.ingest_queue = IngestQueue(deps._ingest_handler)
        await deps.ingest_queue.start()

        async def _restore_queue():
            await deps.ingest_queue.stop()
            deps.ingest_queue = original_queue

        self.addAsyncCleanup(_restore_queue)

        response = await self.client.post("/v1/projects", json={"name": "Skyrim"})
        self.assertEqual(response.status_code, 200)
        self.project_id = response.json()["id"]

    async def _upload(self, name: str, payload: bytes):
        return await self.client.post(
            "/v1/upload",
            files={"file": (name, payload, "application/octet-stream")},
            data={"project_id": self.project_id},
        )

    async def test_an_executable_is_rejected(self):
        response = await self._upload("payload.exe", b"MZ\x90\x00")
        self.assertEqual(response.status_code, 400)
        self.assertIn("PDF and TXT", response.json()["detail"])

    async def test_a_binary_renamed_to_pdf_is_rejected(self):
        response = await self._upload("lore.pdf", b"MZ\x90\x00" * 64)
        self.assertEqual(response.status_code, 400)
        self.assertIn("does not look like a PDF", response.json()["detail"])

    async def test_a_traversing_name_is_rejected_before_it_reaches_disk(self):
        response = await self._upload("../../etc/passwd", b"root:x:0:0")
        self.assertEqual(response.status_code, 400)

    async def test_an_empty_file_is_rejected(self):
        response = await self._upload("empty.txt", b"")
        self.assertEqual(response.status_code, 400)
        self.assertIn("empty", response.json()["detail"].lower())

    async def test_a_file_over_the_cap_is_rejected(self):
        response = await self._upload("huge.txt", b"a" * 4096)
        self.assertEqual(response.status_code, 400)
        self.assertIn("upload limit", response.json()["detail"])

    async def test_nothing_is_left_in_the_staging_directory_after_a_rejection(self):
        from pathlib import Path

        await self._upload("huge.txt", b"a" * 4096)
        staging = Path(self.tmp.name) / ".ingest"
        leftovers = list(staging.glob("upload-*")) if staging.exists() else []
        self.assertEqual(leftovers, [], "an oversized upload leaked its staged temp file")

    async def test_an_upload_that_would_exceed_the_quota_is_rejected(self):
        await self.deps.state_store.register_document(
            self.project_id, "already-there.txt", 1, "sig", size_bytes=4000
        )
        response = await self._upload("more.txt", b"a" * 1024)
        self.assertEqual(response.status_code, 400)
        self.assertIn("quota", response.json()["detail"].lower())

    async def test_a_legitimate_upload_still_succeeds(self):
        response = await self._upload("lore.txt", b"Dragons circled the throat of the world.")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["filename"], "lore.txt")


if __name__ == "__main__":
    unittest.main()
