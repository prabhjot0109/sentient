from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from langchain_core.embeddings import Embeddings


class FakeEmbeddings(Embeddings):
    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 1.0, 0.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


class DocumentsEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(
            os.environ, {"DATA_DIR": self.tmp.name, "VECTOR_BACKEND": "faiss"}
        )
        self.env.start()
        self.addCleanup(self.env.stop)

        # Scoped listing resolves a real ArchivesIngestion, which would otherwise
        # load BAAI/bge-base-en-v1.5 (~9s, and a download on a cold cache).
        embeddings = patch(
            "sentient.adapters.documents.build_embeddings", return_value=FakeEmbeddings()
        )
        embeddings.start()
        self.addCleanup(embeddings.stop)

        from sentient.api import app as api
        from sentient.adapters.auth import IdentityCache
        from sentient.core.config import load_rag_settings
        from sentient.core.cache import ObjectRegistry
        from sentient.services.runtime import RuntimeCache
        from sentient.adapters.state import get_state_store

        # api.py builds these at import time, so a module cached by an earlier test
        # still points at that test's tmpdir. Rebind them the way
        # tests/test_management_endpoints.py does.
        self.api = api
        api._settings = load_rag_settings()
        api.state_store = get_state_store(api._settings)
        api.identity_cache = IdentityCache()
        api.runtime_cache = RuntimeCache()
        api.object_registry = ObjectRegistry()
        api.get_default_archives.cache_clear()
        self.addCleanup(api.get_default_archives.cache_clear)

        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://test"
        )
        self.addAsyncCleanup(self.client.aclose)

    async def _project(self, name: str = "Skyrim") -> str:
        response = await self.client.post("/v1/projects", json={"name": name})
        self.assertEqual(response.status_code, 200)
        return response.json()["id"]

    async def test_documents_endpoint_reports_ingestion_status(self):
        project_id = await self._project()
        await self.api.state_store.register_document(
            project_id, "lore.pdf", 12, "sig-1", status="processing"
        )

        body = (await self.client.get(f"/v1/projects/{project_id}/documents")).json()
        self.assertEqual(len(body["documents"]), 1)
        self.assertEqual(body["documents"][0]["filename"], "lore.pdf")
        self.assertEqual(body["documents"][0]["status"], "processing")

        await self.api.state_store.set_document_status(project_id, "lore.pdf", "ready")
        body = (await self.client.get(f"/v1/projects/{project_id}/documents")).json()
        self.assertEqual(body["documents"][0]["status"], "ready")

    async def test_documents_of_a_foreign_project_are_not_visible(self):
        await self._project()
        response = await self.client.get("/v1/projects/does-not-exist/documents")
        self.assertEqual(response.status_code, 404)

    async def test_sources_listing_is_scoped_to_the_requested_project(self):
        project_id = await self._project()
        # Write a file into the default partition only.
        (Path(self.tmp.name) / "default-only.txt").write_text(
            "shared lore", encoding="utf-8"
        )

        default_body = (await self.client.get("/v1/sources")).json()
        self.assertIn(
            "default-only.txt", [item["name"] for item in default_body["sources"]]
        )

        scoped = (await self.client.get(f"/v1/sources?project_id={project_id}")).json()
        # A project's partition is its own directory; the default file must not leak in.
        self.assertNotIn("default-only.txt", [item["name"] for item in scoped["sources"]])

    async def test_sources_without_params_is_unchanged(self):
        response = await self.client.get("/v1/sources")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("sources", body)
        self.assertIn("count", body)
        self.assertEqual(body["count"], len(body["sources"]))


if __name__ == "__main__":
    unittest.main()
