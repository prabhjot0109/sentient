from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx


class EmbeddingSignatureTests(unittest.TestCase):
    def test_signature_stable_and_dimension_sensitive(self) -> None:
        from sentient.services.runtime import embedding_signature

        base = {
            "embedding_provider": "google",
            "embedding_model": "models/gemini-embedding-001",
            "mrl_vector_size": None,
        }
        self.assertEqual(embedding_signature(base), embedding_signature(dict(base)))
        self.assertNotEqual(
            embedding_signature(base),
            embedding_signature({**base, "mrl_vector_size": 768}),
        )

    def test_model_change_changes_signature(self) -> None:
        from sentient.services.runtime import embedding_signature

        a = embedding_signature({
            "embedding_provider": "google", "embedding_model": "m-a", "mrl_vector_size": None,
        })
        b = embedding_signature({
            "embedding_provider": "google", "embedding_model": "m-b", "mrl_vector_size": None,
        })
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()


class ReindexGuardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"DATA_DIR": self.tmp.name}, clear=False)
        self.env.start()
        for name in ("DATABASE_URL", "NEON_AUTH_JWKS_URL"):
            os.environ.pop(name, None)

        import api
        from sentient.adapters.auth import IdentityCache
        from sentient.core.config import load_rag_settings
        from sentient.core.cache import ObjectRegistry
        from sentient.services.runtime import RuntimeCache
        from sentient.adapters.state import get_state_store

        self.api = api
        api._settings = load_rag_settings()
        api.state_store = get_state_store(api._settings)
        api.identity_cache = IdentityCache()
        api.runtime_cache = RuntimeCache()
        api.object_registry = ObjectRegistry()

    async def asyncTearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()

    async def test_embedding_change_requires_reindex_and_enqueues_once(self) -> None:
        with patch.object(self.api, "enqueue_reindex", new_callable=AsyncMock) as enqueue:
            transport = httpx.ASGITransport(app=self.api.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                project = await client.post("/v1/projects", json={"name": "P"})
                response = await client.put(
                    f"/v1/projects/{project.json()['id']}/config",
                    json={"embedding_model_name": "models/other-embedding"},
                )

        self.assertEqual(response.status_code, 200)
        project_id = project.json()["id"]
        stored = await self.api.state_store.get_project(project.json()["user_id"], project_id)
        self.assertEqual(stored["status"], "reindexing_required")
        enqueue.assert_awaited_once()

    async def test_reindexing_project_blocks_completions(self) -> None:
        user = await self.api.state_store.ensure_user(None)
        project = await self.api.state_store.create_project(user["id"], "P")
        await self.api.state_store.set_project_status(project["id"], "reindexing_required")
        ctx = await self.api.runtime_cache.resolve(
            self.api.state_store,
            self.api._settings,
            user_id=user["id"],
            user_key="default",
            project_id=project["id"],
        )
        request = self.api.ChatCompletionRequest(messages=[{"role": "user", "content": "hi"}])

        with self.assertRaises(self.api.HTTPException) as raised:
            await self.api._run_completions(request, ctx)

        self.assertEqual(raised.exception.status_code, 409)

    async def test_reindex_handler_purges_then_restores_project(self) -> None:
        from sentient.core.concurrency import ReindexJob

        user = await self.api.state_store.ensure_user(None)
        project = await self.api.state_store.create_project(user["id"], "P")
        await self.api.state_store.register_document(
            project["id"], "lore.txt", 3, "old-signature", status="ready"
        )
        await self.api.state_store.set_project_status(project["id"], "reindexing_required")
        archives = SimpleNamespace(
            data_dir=Path(self.tmp.name),
            settings=SimpleNamespace(vector_backend="qdrant"),
            clear_project=Mock(),
            reset_index=Mock(),
            add_file=AsyncMock(return_value={"added_chunk_count": 5}),
        )

        with patch.object(self.api, "get_archives", return_value=archives):
            await self.api._reindex_handler(
                ReindexJob(project["id"], "user-key", None, "new-signature")
            )

        archives.clear_project.assert_called_once_with("user-key", project["id"])
        archives.add_file.assert_awaited_once_with(
            str(Path(self.tmp.name) / "lore.txt"),
            user_key="user-key",
            project_id=project["id"],
            embedding_signature="new-signature",
        )
        document = (await self.api.state_store.list_documents(project["id"]))[0]
        self.assertEqual(document["status"], "ready")
        self.assertEqual(document["embedding_signature"], "new-signature")
        stored = await self.api.state_store.get_project(user["id"], project["id"])
        self.assertEqual(stored["status"], "active")
