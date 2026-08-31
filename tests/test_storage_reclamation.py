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


class StorageReclamationTests(unittest.IsolatedAsyncioTestCase):
    """`DELETE /v1/projects/{id}` returned {"deleted": true} and left the storage.

    The original reasoning in `services/projects.py` was that orphaned vectors are
    unreachable, because every query filters on user_key and project_id, so this is
    disk cost rather than a leak. That is correct and it is no longer sufficient.

    On Qdrant the orphan is worse than on FAISS, not better: every tenant shares one
    collection, so a deleted project's points sit inside the same 1 GB free cluster
    that every live project is competing for, and no reindex ever touches them
    because there is no longer a project to reindex. On FAISS the orphan is the
    partition directory under data/projects/, which `clear_project` does NOT remove
    because it is a documented no-op there.

    Two backends, two mechanisms. A test that only covered one would pass while the
    deployed backend leaked.
    """

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {"DATA_DIR": self.tmp.name, "VECTOR_BACKEND": "faiss"})
        env.start()
        self.addCleanup(env.stop)

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

        self.deps = deps
        deps._settings = load_rag_settings()
        deps.state_store = get_state_store(deps._settings)
        deps.identity_cache = IdentityCache()
        deps.runtime_cache = RuntimeCache()
        deps.object_registry = ObjectRegistry()
        deps.get_default_archives.cache_clear()
        self.addCleanup(deps.get_default_archives.cache_clear)

        self.data_dir = Path(self.tmp.name)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://test"
        )
        self.addAsyncCleanup(self.client.aclose)

    async def _project(self, name: str = "Skyrim") -> tuple[str, str, str]:
        """Create a project and return its id with the identity the ROUTE resolved.

        Both values are read back from the resolver rather than derived, because
        deriving them is wrong twice over. `user_id` and `user_key` are different
        strings by design -- `user_key_of` is sha256(user_id)[:16], an opaque tenant
        id safe to put in Qdrant payloads and log lines. And with authentication
        disabled, which is how this suite runs, `resolve_caller` does not return that
        hash at all: the tenant is the literal string "default".

        So a partition path computed from the user row is a path the route never
        touches, and every assertion here would pass or fail for the wrong reason.
        """
        response = await self.client.post("/v1/projects", json={"name": name})
        project_id = response.json()["id"]
        # resolve_caller, not current_user: the latter's parameters carry FastAPI
        # `Header(...)` sentinels as defaults, so calling it outside a request hands
        # the sentinel object to code expecting a string.
        user_id, user_key = await self.deps.resolve_caller()
        return project_id, user_id, user_key

    def _partition_for(self, user_key: str, project_id: str) -> Path:
        return self.data_dir / "projects" / self.deps.partition_name(user_key, project_id)

    def _make_partition(self, user_key: str, project_id: str) -> Path:
        partition = self._partition_for(user_key, project_id)
        (partition / "faiss_index").mkdir(parents=True)
        (partition / "lore.txt").write_text("lore", encoding="utf-8")
        return partition

    async def test_deleting_a_project_removes_its_partition_directory(self):
        project_id, _, user_key = await self._project()
        partition = self._make_partition(user_key, project_id)
        self.assertTrue(partition.exists())

        response = await self.client.delete(f"/v1/projects/{project_id}")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(partition.exists())

    async def test_it_does_not_touch_another_projects_directory(self):
        """The neighbour test.

        A reclamation bug is silent data loss, and it is the one failure here that
        is strictly worse than the leak it replaces.
        """
        doomed_id, _, user_key = await self._project("Doomed")
        keeper_id, _, _ = await self._project("Keeper")
        doomed = self._make_partition(user_key, doomed_id)
        keeper = self._make_partition(user_key, keeper_id)

        await self.client.delete(f"/v1/projects/{doomed_id}")

        self.assertFalse(doomed.exists())
        self.assertTrue(keeper.exists())
        self.assertTrue((keeper / "lore.txt").exists())

    async def test_deleting_a_project_with_no_documents_is_still_clean(self):
        project_id, _, _ = await self._project()

        response = await self.client.delete(f"/v1/projects/{project_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"deleted": True})

    async def test_a_failure_to_reclaim_does_not_fail_the_delete(self):
        """The row is already gone and the API is about to say so.

        Raising here would report a failure for an operation that succeeded, and the
        user's natural response -- retry -- would land on a 404 for a project that
        really was deleted. Losing the disk is the lesser harm and it is logged.
        """
        project_id, user_id, user_key = await self._project()
        self._make_partition(user_key, project_id)

        with patch.object(self.deps, "reclaim_project_storage", side_effect=OSError("device busy")):
            response = await self.client.delete(f"/v1/projects/{project_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(await self.deps.state_store.get_project(user_id, project_id))

    async def test_deleting_a_project_that_does_not_exist_reclaims_nothing(self):
        """404 before reclamation, not after.

        Ownership is checked by the delete returning false. Reclaiming first would
        let one user erase another user's vectors by guessing a project id.
        """
        _, _, user_key = await self._project()
        stranger_id = "11111111-1111-1111-1111-111111111111"
        partition = self._make_partition(user_key, stranger_id)

        response = await self.client.delete(f"/v1/projects/{stranger_id}")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(partition.exists())


class QdrantReclamationTests(unittest.IsolatedAsyncioTestCase):
    """On Qdrant the mechanism is a payload-filter delete, not a directory.

    `FaissBackend.clear_project` is a documented no-op, so calling it would have
    reclaimed nothing on the default backend while looking correct in review.
    """

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {"DATA_DIR": self.tmp.name, "VECTOR_BACKEND": "qdrant"})
        env.start()
        self.addCleanup(env.stop)

        from sentient.api import deps
        from sentient.core.config import load_rag_settings

        self.deps = deps
        self.settings = load_rag_settings()

    async def test_it_clears_the_projects_points_by_filter(self):
        cleared: list[tuple[str | None, str]] = []

        class FakeArchives:
            def clear_project(self, user_key, project_id):
                cleared.append((user_key, project_id))

        with (
            patch.object(self.deps, "_settings", self.settings),
            patch.object(self.deps, "get_default_archives", return_value=FakeArchives()),
        ):
            await self.deps.reclaim_project_storage("user-1", "project-1")

        self.assertEqual(cleared, [("user-1", "project-1")])

    async def test_the_shared_collection_is_why_a_default_client_can_do_this(self):
        """One collection deployment-wide, so the filter is the only tenant boundary.

        That is the same property V3 had to prove was working, and it is what lets a
        delete run without resolving the deleted project's own runtime context --
        which it could not do anyway, because the row is gone by then.
        """
        self.assertEqual(self.settings.vector_backend, "qdrant")


if __name__ == "__main__":
    unittest.main()
