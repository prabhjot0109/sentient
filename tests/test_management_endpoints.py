from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx


class ManagementEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"DATA_DIR": self.tmp.name}, clear=False)
        self.env.start()
        for name in ("DATABASE_URL", "NEON_AUTH_JWKS_URL"):
            os.environ.pop(name, None)

        from sentient.api import app as api
        from sentient.api import deps
        from sentient.adapters.auth import IdentityCache
        from sentient.core.config import load_rag_settings
        from sentient.core.cache import ObjectRegistry
        from sentient.services.runtime import RuntimeCache
        from sentient.adapters.state import get_state_store

        self.api = api
        self.deps = deps
        deps._settings = load_rag_settings()
        deps.state_store = get_state_store(deps._settings)
        deps.identity_cache = IdentityCache()
        deps.runtime_cache = RuntimeCache()
        deps.object_registry = ObjectRegistry()

    async def asyncTearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()

    async def test_key_project_config_and_persona_flow(self) -> None:
        invalidate_patcher = patch.object(
            self.deps.runtime_cache,
            "invalidate",
            wraps=self.deps.runtime_cache.invalidate,
        )
        invalidate = invalidate_patcher.start()
        self.addCleanup(invalidate_patcher.stop)
        transport = httpx.ASGITransport(app=self.api.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            key = await client.post("/v1/keys", json={"label": "mantella"})
            self.assertEqual(key.status_code, 200)
            self.assertTrue(key.json()["api_key"].startswith("sk-sent-"))

            keys = await client.get("/v1/keys")
            self.assertEqual(keys.status_code, 200)
            self.assertNotIn("key_hash", keys.json()["keys"][0])

            project = await client.post(
                "/v1/projects",
                json={"name": "Skyrim", "base_preset": "skyrim"},
            )
            self.assertEqual(project.status_code, 200)
            project_id = project.json()["id"]

            config = await client.put(
                f"/v1/projects/{project_id}/config",
                json={"model_name": "gemini-2.5-flash", "rag_top_k": 6},
            )
            self.assertEqual(config.status_code, 200)
            self.assertEqual(config.json()["model_name"], "gemini-2.5-flash")
            self.assertEqual(config.json()["rag_top_k"], 6)

            persona = await client.put(
                f"/v1/projects/{project_id}/persona",
                json={"system_prompt": "You are the voice of Skyrim."},
            )
            self.assertEqual(persona.status_code, 200)
            self.assertEqual(persona.json()["persona_prompt"], "You are the voice of Skyrim.")

            presets = await client.get("/v1/presets")
            self.assertEqual(presets.status_code, 200)
            self.assertIn("skyrim", presets.json()["presets"])

            projects = await client.get("/v1/projects")
            self.assertEqual(projects.status_code, 200)
            self.assertEqual(projects.json()["projects"][0]["id"], project_id)

        self.assertEqual(invalidate.call_count, 2)
        invalidate.assert_any_call(project_id)

    async def test_project_upload_is_scoped_and_reports_processing(self) -> None:
        from sentient.adapters.auth import hash_key, user_key_of

        owner = await self.deps.state_store.ensure_user("upload-owner")
        raw_key = "sk-sent-upload"
        await self.deps.state_store.create_api_key(owner["id"], hash_key(raw_key))
        project = await self.deps.state_store.create_project(owner["id"], "Skyrim")
        archives = SimpleNamespace(data_dir=Path(self.tmp.name) / "project-data")

        with (
            patch.object(self.deps, "get_archives_for_context",
                new_callable=AsyncMock,
                return_value=archives,
            ),
            patch.object(
                self.api, "enqueue_ingest", new_callable=AsyncMock
            ) as enqueue,
        ):
            transport = httpx.ASGITransport(app=self.api.app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/v1/upload",
                    headers={"X-API-Key": raw_key},
                    data={"project_id": project["id"]},
                    files={"file": ("lore.txt", b"project lore", "text/plain")},
                )
                documents = await self.deps.state_store.list_documents(project["id"])

        self.assertEqual(response.status_code, 202)
        job = enqueue.await_args.args[0]
        self.assertEqual(job.user_key, user_key_of(raw_key))
        self.assertEqual(job.project_id, project["id"])
        self.assertEqual(documents[0]["status"], "processing")
        Path(job.file_path).unlink(missing_ok=True)

    async def test_revoked_key_is_rejected_immediately(self) -> None:
        transport = httpx.ASGITransport(app=self.api.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post("/v1/keys", json={"label": "temporary"})
            raw_key = created.json()["api_key"]
            key_id = created.json()["id"]

            warm = await client.get("/v1/projects", headers={"X-API-Key": raw_key})
            self.assertEqual(warm.status_code, 200)

            revoked = await client.delete(f"/v1/keys/{key_id}")
            self.assertEqual(revoked.status_code, 200)
            self.assertTrue(revoked.json()["revoked"])

            rejected = await client.get("/v1/projects", headers={"X-API-Key": raw_key})

        self.assertEqual(rejected.status_code, 401)

    async def test_config_rejects_unknown_fields(self) -> None:
        transport = httpx.ASGITransport(app=self.api.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project = await client.post("/v1/projects", json={"name": "Skyrim"})
            response = await client.put(
                f"/v1/projects/{project.json()['id']}/config",
                json={"rag_top_kk": 99},
            )

        self.assertEqual(response.status_code, 422)

    async def test_management_requires_identity_when_auth_is_configured(self) -> None:
        from dataclasses import replace

        self.deps._settings = replace(
            self.deps._settings,
            neon_auth_jwks_url="https://auth.example/.well-known/jwks.json",
        )
        transport = httpx.ASGITransport(app=self.api.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/projects")

        self.assertEqual(response.status_code, 401)

    async def test_cannot_edit_another_users_project(self) -> None:
        from sentient.adapters.auth import hash_key

        owner = await self.deps.state_store.ensure_user("owner")
        other = await self.deps.state_store.ensure_user("other")
        project = await self.deps.state_store.create_project(owner["id"], "Private")
        await self.deps.state_store.create_api_key(other["id"], hash_key("sk-sent-other"))

        transport = httpx.ASGITransport(app=self.api.app)
        headers = {"X-API-Key": "sk-sent-other"}
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            config = await client.put(
                f"/v1/projects/{project['id']}/config",
                json={"rag_top_k": 8},
                headers=headers,
            )
            persona = await client.put(
                f"/v1/projects/{project['id']}/persona",
                json={"system_prompt": "Not yours"},
                headers=headers,
            )

        self.assertEqual(config.status_code, 404)
        self.assertEqual(persona.status_code, 404)


if __name__ == "__main__":
    unittest.main()
