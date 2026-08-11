from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

import httpx
from langchain_core.embeddings import Embeddings


class FakeEmbeddings(Embeddings):
    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 1.0, 0.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


class LifecycleEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(
            os.environ, {"DATA_DIR": self.tmp.name, "VECTOR_BACKEND": "faiss"}
        )
        self.env.start()
        self.addCleanup(self.env.stop)

        embeddings = patch(
            "logic.ingestion.build_embeddings", return_value=FakeEmbeddings()
        )
        embeddings.start()
        self.addCleanup(embeddings.stop)

        import api
        from logic.auth import IdentityCache
        from logic.config import load_rag_settings
        from logic.registry import ObjectRegistry
        from logic.runtime import RuntimeCache
        from logic.state import get_state_store

        # api.py builds these at import time; rebind them so this test does not
        # inherit an earlier test's tmpdir (see tests/test_management_endpoints.py).
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

    async def _project(self, name="Skyrim") -> str:
        return (await self.client.post("/v1/projects", json={"name": name})).json()["id"]

    async def test_rename_project(self):
        project_id = await self._project()
        response = await self.client.patch(
            f"/v1/projects/{project_id}", json={"name": "Fallout 4"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Fallout 4")

        listed = (await self.client.get("/v1/projects")).json()["projects"]
        self.assertEqual([p["name"] for p in listed], ["Fallout 4"])

    async def test_renaming_an_unknown_project_is_404(self):
        response = await self.client.patch("/v1/projects/nope", json={"name": "X"})
        self.assertEqual(response.status_code, 404)

    async def test_an_empty_name_is_rejected(self):
        project_id = await self._project()
        response = await self.client.patch(f"/v1/projects/{project_id}", json={"name": ""})
        self.assertEqual(response.status_code, 422)

    async def test_delete_project_removes_it_from_the_listing(self):
        project_id = await self._project()
        response = await self.client.delete(f"/v1/projects/{project_id}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])

        self.assertEqual((await self.client.get("/v1/projects")).json()["projects"], [])
        self.assertEqual(
            (await self.client.get(f"/v1/projects/{project_id}/threads")).status_code, 404
        )

    async def test_deleting_a_project_invalidates_its_runtime_cache(self):
        project_id = await self._project()
        with patch.object(self.api.runtime_cache, "invalidate") as invalidate:
            await self.client.delete(f"/v1/projects/{project_id}")
        invalidate.assert_called_once_with(project_id)

    async def test_a_failed_delete_does_not_invalidate_anything(self):
        with patch.object(self.api.runtime_cache, "invalidate") as invalidate:
            await self.client.delete("/v1/projects/nope")
        invalidate.assert_not_called()

    async def test_deleting_an_unknown_project_is_404(self):
        self.assertEqual(
            (await self.client.delete("/v1/projects/nope")).status_code, 404
        )

    async def test_delete_thread(self):
        project_id = await self._project()
        thread = await self.api.state_store.upsert_thread(
            project_id, "sess-1", title="First chat"
        )
        response = await self.client.delete(f"/v1/threads/{thread['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            (await self.client.get(f"/v1/projects/{project_id}/threads")).json()["threads"], []
        )

    async def test_deleting_an_unknown_thread_is_404(self):
        self.assertEqual((await self.client.delete("/v1/threads/nope")).status_code, 404)

    async def test_deleting_a_project_source_clears_its_document_row(self):
        project_id = await self._project()
        await self.api.state_store.register_document(
            project_id, "lore.txt", 1, "sig", status="ready"
        )
        ctx = await self.api._completions_ctx(None, project_id)
        archives = await self.api.get_archives_for_context(ctx)
        archives.data_dir.mkdir(parents=True, exist_ok=True)
        (archives.data_dir / "lore.txt").write_text("some lore", encoding="utf-8")

        response = await self.client.delete(f"/v1/sources/lore.txt?project_id={project_id}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        # The ghost row is the bug being fixed: the file is gone, the row must be too.
        self.assertEqual(
            (await self.client.get(f"/v1/projects/{project_id}/documents")).json()["documents"], []
        )

    async def test_deleting_a_missing_source_is_still_404(self):
        response = await self.client.delete("/v1/sources/nothing-here.txt")
        self.assertEqual(response.status_code, 404)

    async def test_a_missing_project_source_is_404_not_500(self):
        # A blanket `except Exception -> 500` around the delete body would swallow
        # this HTTPException; R7's delta records that exact regression.
        project_id = await self._project()
        response = await self.client.delete(
            f"/v1/sources/absent.txt?project_id={project_id}"
        )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
