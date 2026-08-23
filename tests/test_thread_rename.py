"""B3: `PATCH /v1/threads/{id}`.

threads.py had GET list, DELETE and GET messages but no PATCH, so F5's rename
was unimplementable. The ownership check is the same one DELETE uses.
"""

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


class ThreadRenameTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {"DATA_DIR": self.tmp.name, "VECTOR_BACKEND": "faiss"})
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

    async def _project(self, name: str = "Skyrim") -> str:
        response = await self.client.post("/v1/projects", json={"name": name})
        self.assertEqual(response.status_code, 200)
        return response.json()["id"]

    async def test_patch_renames_the_thread(self):
        project_id = await self._project()
        thread = await self.deps.state_store.upsert_thread(project_id, "s1", title="New chat")

        response = await self.client.patch(
            f"/v1/threads/{thread['id']}", json={"title": "Talking to Lydia"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Talking to Lydia")

        listed = (await self.client.get(f"/v1/projects/{project_id}/threads")).json()["threads"]
        self.assertEqual(listed[0]["title"], "Talking to Lydia")

    async def test_a_rename_replaces_the_title_rather_than_coalescing_it(self):
        """The reason upsert_thread cannot serve this route: its COALESCE keeps the
        existing title, so a second rename would silently do nothing."""
        project_id = await self._project()
        thread = await self.deps.state_store.upsert_thread(project_id, "s1", title="New chat")

        await self.client.patch(f"/v1/threads/{thread['id']}", json={"title": "First"})
        response = await self.client.patch(f"/v1/threads/{thread['id']}", json={"title": "Second"})

        self.assertEqual(response.json()["title"], "Second")

    async def test_patching_someone_elses_thread_is_404(self):
        stranger = await self.deps.state_store.ensure_user("stranger")
        theirs = await self.deps.state_store.create_project(stranger["id"], "Fallout")
        thread = await self.deps.state_store.upsert_thread(theirs["id"], "s1")

        response = await self.client.patch(f"/v1/threads/{thread['id']}", json={"title": "x"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            (await self.deps.state_store.get_thread(stranger["id"], thread["id"]))["title"],
            thread["title"],
        )

    async def test_an_empty_title_is_rejected(self):
        """min_length alone accepts "   ", which renders as an invisible sidebar row."""
        project_id = await self._project()
        thread = await self.deps.state_store.upsert_thread(project_id, "s1")
        response = await self.client.patch(f"/v1/threads/{thread['id']}", json={"title": "   "})
        self.assertEqual(response.status_code, 422)

    async def test_a_title_is_stored_trimmed(self):
        project_id = await self._project()
        thread = await self.deps.state_store.upsert_thread(project_id, "s1")
        response = await self.client.patch(
            f"/v1/threads/{thread['id']}", json={"title": "  Talking to Lydia  "}
        )
        self.assertEqual(response.json()["title"], "Talking to Lydia")

    async def test_an_unknown_thread_is_404(self):
        response = await self.client.patch("/v1/threads/nope", json={"title": "x"})
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
