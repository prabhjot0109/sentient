"""Which credential each route accepts, asserted as a three-way matrix.

JWT, API key, no credential -- per route. The no-credential case is the one that
regressed silently (spec A3: `completions_ctx` resolved identity without the
auth-enabled 401 that `current_user` applies), so it is asserted on every route
rather than once. Auth is ON for every test here, because that is the condition
the defects only appear under and the condition the product ships in.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from langchain_core.embeddings import Embeddings

from sentient.adapters.auth import hash_key

JWKS = "https://neon.example/jwks"
RAW_KEY = "sk-sent-matrix"


class FakeEmbeddings(Embeddings):
    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 1.0, 0.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


class _AuthenticatedApp:
    """Shared fixture: the app with auth ON, one owner, one key, one project.

    A mixin rather than a base TestCase on purpose. pytest collects every
    unittest.TestCase subclass regardless of its name, so a shared base class
    would re-run each of its own tests once per subclass, rebuilding this
    fixture every time for no added coverage.
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

        self.api = api
        self.deps = deps

        # Restoring every singleton this class rebinds is not optional. They are
        # module-level by design (spec 7.2), so a class that leaves auth switched
        # on in deps._settings hands every later test file a 401. That same leak,
        # arriving from a populated .env, is what made this suite red before.
        original = (
            deps._settings,
            deps.state_store,
            deps.identity_cache,
            deps.runtime_cache,
            deps.object_registry,
        )

        def _restore():
            (
                deps._settings,
                deps.state_store,
                deps.identity_cache,
                deps.runtime_cache,
                deps.object_registry,
            ) = original

        self.addCleanup(_restore)

        deps._settings = replace(load_rag_settings(), neon_auth_jwks_url=JWKS)
        deps.state_store = get_state_store(deps._settings)
        deps.identity_cache = IdentityCache()
        deps.runtime_cache = RuntimeCache()
        deps.object_registry = ObjectRegistry()
        deps.get_default_archives.cache_clear()
        self.addCleanup(deps.get_default_archives.cache_clear)

        verify = patch(
            "sentient.adapters.auth.verify_jwt",
            return_value={"sub": "neon-sub-matrix", "email": "m@example.com"},
        )
        verify.start()
        self.addCleanup(verify.stop)

        self.owner = await deps.state_store.ensure_user("neon-sub-matrix", "m@example.com")
        await deps.state_store.create_api_key(self.owner["id"], hash_key(RAW_KEY))
        self.project = await deps.state_store.create_project(self.owner["id"], "Skyrim")

        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://test"
        )
        self.addAsyncCleanup(self.client.aclose)

    def _archives_patch(self):
        archives = SimpleNamespace(
            data_dir=Path(self.tmp.name) / "partition",
            list_sources=lambda: [],
        )
        return patch.object(
            self.deps, "get_archives_for_context", new_callable=AsyncMock, return_value=archives
        )


class AuthMatrixTests(_AuthenticatedApp, unittest.IsolatedAsyncioTestCase):
    async def test_upload_rejects_a_request_with_no_credential(self):
        response = await self.client.post(
            "/v1/upload",
            data={"project_id": self.project["id"]},
            files={"file": ("lore.txt", b"lore", "text/plain")},
        )
        self.assertEqual(response.status_code, 401)

    async def test_upload_accepts_a_bearer_jwt(self):
        with (
            self._archives_patch(),
            patch.object(self.deps, "enqueue_ingest", new_callable=AsyncMock) as enqueue,
        ):
            response = await self.client.post(
                "/v1/upload",
                headers={"Authorization": "Bearer console-token"},
                data={"project_id": self.project["id"]},
                files={"file": ("lore.txt", b"lore", "text/plain")},
            )
            self.assertEqual(response.status_code, 202)
            Path(enqueue.await_args.args[0].file_path).unlink(missing_ok=True)

    async def test_upload_accepts_an_api_key(self):
        with (
            self._archives_patch(),
            patch.object(self.deps, "enqueue_ingest", new_callable=AsyncMock) as enqueue,
        ):
            response = await self.client.post(
                "/v1/upload",
                headers={"X-API-Key": RAW_KEY},
                data={"project_id": self.project["id"]},
                files={"file": ("lore.txt", b"lore", "text/plain")},
            )
            self.assertEqual(response.status_code, 202)
            Path(enqueue.await_args.args[0].file_path).unlink(missing_ok=True)

    async def test_jwt_and_api_key_upload_into_the_same_partition(self):
        """The cross-surface assertion: G1 and G2 are only correct together."""
        captured: list[str] = []
        with (
            self._archives_patch(),
            patch.object(self.deps, "enqueue_ingest", new_callable=AsyncMock) as enqueue,
        ):
            for headers in ({"Authorization": "Bearer console-token"}, {"X-API-Key": RAW_KEY}):
                await self.client.post(
                    "/v1/upload",
                    headers=headers,
                    data={"project_id": self.project["id"]},
                    files={"file": ("lore.txt", b"lore", "text/plain")},
                )
                job = enqueue.await_args.args[0]
                captured.append(job.user_key)
                Path(job.file_path).unlink(missing_ok=True)

        self.assertEqual(captured[0], captured[1])

    async def test_sources_rejects_a_request_with_no_credential(self):
        response = await self.client.get("/v1/sources", params={"project_id": self.project["id"]})
        self.assertEqual(response.status_code, 401)

    async def test_sources_accepts_a_bearer_jwt(self):
        with self._archives_patch():
            response = await self.client.get(
                "/v1/sources",
                params={"project_id": self.project["id"]},
                headers={"Authorization": "Bearer console-token"},
            )
        self.assertEqual(response.status_code, 200)

    async def test_delete_source_rejects_a_request_with_no_credential(self):
        response = await self.client.delete(
            "/v1/sources/lore.txt", params={"project_id": self.project["id"]}
        )
        self.assertEqual(response.status_code, 401)

    async def test_a_non_bearer_authorization_header_is_rejected(self):
        response = await self.client.get(
            "/v1/sources",
            params={"project_id": self.project["id"]},
            headers={"Authorization": "Basic Zm9vOmJhcg=="},
        )
        self.assertEqual(response.status_code, 401)


class RetrieveScopingTests(_AuthenticatedApp, unittest.IsolatedAsyncioTestCase):
    """`/v1/retrieve` was the only route with no dependency, no header and no
    project scoping -- a raw lore read open to anyone who could reach the port."""

    async def test_retrieve_rejects_a_request_with_no_credential(self):
        response = await self.client.post(
            "/v1/retrieve", json={"query": "dragons", "project_id": self.project["id"]}
        )
        self.assertEqual(response.status_code, 401)

    async def test_retrieve_scopes_to_the_callers_tenant_and_project(self):
        from sentient.adapters.auth import user_key_of

        captured: dict[str, object] = {}

        class _StubArchives:
            async def retrieve(self, *args, **kwargs):
                captured.update(kwargs)
                return []

        with patch.object(
            self.deps,
            "get_archives_for_context",
            new_callable=AsyncMock,
            return_value=_StubArchives(),
        ):
            response = await self.client.post(
                "/v1/retrieve",
                headers={"Authorization": "Bearer console-token"},
                json={"query": "dragons", "project_id": self.project["id"]},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["project_id"], self.project["id"])
        self.assertEqual(captured["user_key"], user_key_of(self.owner["id"]))

    async def test_retrieve_404s_on_a_project_the_caller_does_not_own(self):
        stranger = await self.deps.state_store.ensure_user("someone-else")
        theirs = await self.deps.state_store.create_project(stranger["id"], "Fallout")
        response = await self.client.post(
            "/v1/retrieve",
            headers={"Authorization": "Bearer console-token"},
            json={"query": "dragons", "project_id": theirs["id"]},
        )
        self.assertEqual(response.status_code, 404)
