from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import httpx
from cryptography.fernet import Fernet, InvalidToken

from sentient.adapters.state.sqlite_store import SQLiteStateStore
from sentient.core.config import load_rag_settings
from sentient.core.crypto import decrypt_key
from sentient.services.runtime import RuntimeCache


class CryptoPrimitiveTests(unittest.TestCase):
    def setUp(self):
        self.secret = Fernet.generate_key().decode()

    def test_roundtrip(self):
        from sentient.core.crypto import decrypt_key, encrypt_key

        token = encrypt_key("AIza-super-secret", self.secret)
        self.assertNotIn("super-secret", token)  # ciphertext, not plaintext
        self.assertEqual(decrypt_key(token, self.secret), "AIza-super-secret")

    def test_hint_shows_only_tail(self):
        from sentient.core.crypto import key_hint

        self.assertEqual(key_hint("sk-abcdefgh1234"), "…1234")

    def test_wrong_secret_fails_loudly(self):
        from sentient.core.crypto import decrypt_key, encrypt_key

        token = encrypt_key("k", self.secret)
        # Narrow on purpose: a blind `Exception` would also pass on a TypeError
        # from a signature change, hiding the fact that the crypto stopped working.
        with self.assertRaises(InvalidToken):
            decrypt_key(token, Fernet.generate_key().decode())


class CredentialStoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SQLiteStateStore(str(Path(self.tmp.name) / "state.db"))

    def tearDown(self):
        self.tmp.cleanup()

    async def test_upsert_replaces_and_list_never_leaks_ciphertext(self):
        user = await self.store.ensure_user("A")
        await self.store.upsert_credential(user["id"], "google", "cipher-1", "…1111")
        await self.store.upsert_credential(user["id"], "google", "cipher-2", "…2222")
        stored = await self.store.get_credential(user["id"], "google")
        self.assertEqual(stored["encrypted_key"], "cipher-2")
        listed = await self.store.list_credentials(user["id"])
        self.assertEqual(
            listed,
            [{"provider": "google", "key_hint": "…2222", "created_at": stored["created_at"]}],
        )

    async def test_user_cannot_read_or_delete_another_users_credential(self):
        owner = await self.store.ensure_user("owner")
        other = await self.store.ensure_user("other")
        await self.store.upsert_credential(owner["id"], "openai", "cipher", "…abcd")
        self.assertIsNone(await self.store.get_credential(other["id"], "openai"))
        self.assertFalse(await self.store.delete_credential(other["id"], "openai"))


class CredentialResolutionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SQLiteStateStore(str(Path(self.tmp.name) / "state.db"))
        self.secret = Fernet.generate_key().decode()
        self.settings = replace(load_rag_settings(), sentient_secret_key=self.secret)

    def tearDown(self):
        self.tmp.cleanup()

    async def test_stored_credentials_override_env_floor_and_change_signature(self):
        from sentient.core.crypto import encrypt_key
        from sentient.services.runtime import resolve_runtime_context

        user = await self.store.ensure_user("A")
        project = await self.store.create_project(user["id"], "P")
        await self.store.upsert_project_config(
            project["id"], llm_provider="google", embedding_provider="openai"
        )
        before = await resolve_runtime_context(
            self.store, self.settings, user_id=user["id"], user_key="u", project_id=project["id"]
        )
        await self.store.upsert_credential(
            user["id"], "google", encrypt_key("google-secret", self.secret), "…cret"
        )
        await self.store.upsert_credential(
            user["id"], "openai", encrypt_key("openai-secret", self.secret), "…cret"
        )
        resolved = await resolve_runtime_context(
            self.store, self.settings, user_id=user["id"], user_key="u", project_id=project["id"]
        )
        self.assertEqual(resolved.llm_settings["api_key"], "google-secret")
        self.assertEqual(resolved.rag_settings["embedding_api_key"], "openai-secret")
        self.assertNotEqual(resolved.config_signature, before.config_signature)

    async def test_embedding_key_follows_the_project_provider_not_the_env_default(self):
        """A project may override embedding_provider; the key must follow it."""
        from sentient.services.runtime import resolve_runtime_context

        user = await self.store.ensure_user("A")
        project = await self.store.create_project(user["id"], "P")
        await self.store.upsert_project_config(project["id"], embedding_provider="openai")
        env = {"OPENAI_API_KEY": "sk-env-openai", "GOOGLE_API_KEY": "AIza-env-google"}
        with patch.dict(os.environ, env, clear=False):
            settings = replace(
                load_rag_settings(), embedding_provider="google", sentient_secret_key=None
            )
            resolved = await resolve_runtime_context(
                self.store, settings, user_id=user["id"], user_key="u", project_id=project["id"]
            )
        self.assertEqual(resolved.rag_settings["embedding_api_key"], "sk-env-openai")

    async def test_explicit_provider_key_beats_the_stored_key(self):
        from sentient.core.crypto import encrypt_key
        from sentient.services.runtime import resolve_runtime_context

        user = await self.store.ensure_user("A")
        project = await self.store.create_project(user["id"], "P")
        await self.store.upsert_project_config(project["id"], llm_provider="openai")
        await self.store.upsert_credential(
            user["id"], "openai", encrypt_key("stored-key", self.secret), "…-key"
        )
        resolved = await resolve_runtime_context(
            self.store,
            self.settings,
            user_id=user["id"],
            user_key="u",
            project_id=project["id"],
            provider_key="sk-explicit-key",
        )
        self.assertEqual(resolved.llm_settings["api_key"], "sk-explicit-key")


class CredentialEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from sentient.api import app as api
        from sentient.api import deps

        self.api = api
        self.deps = deps
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SQLiteStateStore(str(Path(self.tmp.name) / "state.db"))
        self.secret = Fernet.generate_key().decode()
        self.original = (deps.state_store, deps._settings, deps.runtime_cache)
        deps.state_store = self.store
        deps._settings = replace(deps._settings, sentient_secret_key=self.secret)
        deps.runtime_cache = RuntimeCache()
        self.user = await self.store.ensure_user(None)
        transport = httpx.ASGITransport(app=api.app)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.deps.state_store, self.deps._settings, self.deps.runtime_cache = self.original
        self.api.app.dependency_overrides.clear()
        self.tmp.cleanup()

    async def test_endpoint_returns_hints_only_and_persists_ciphertext(self):
        raw_key = "sk-provided-key-1234"
        created = await self.client.post(
            "/v1/credentials", json={"provider": "openai", "api_key": raw_key}
        )
        self.assertEqual(created.status_code, 200)
        self.assertNotIn(raw_key, created.text)
        self.assertEqual(created.json(), {"provider": "openai", "key_hint": "…1234"})

        listed = await self.client.get("/v1/credentials")
        self.assertNotIn("encrypted_key", listed.text)
        self.assertNotIn(raw_key, listed.text)
        self.assertEqual([row["provider"] for row in listed.json()["credentials"]], ["openai"])

        # The database must hold ciphertext only, and it must decrypt to the original.
        stored = await self.store.get_credential(self.user["id"], "openai")
        self.assertNotIn(raw_key, stored["encrypted_key"])
        self.assertEqual(decrypt_key(stored["encrypted_key"], self.secret), raw_key)

    async def test_delete_removes_the_credential(self):
        await self.client.post("/v1/credentials", json={"provider": "groq", "api_key": "gsk_abcd"})
        deleted = await self.client.delete("/v1/credentials/groq")
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.json()["deleted"])
        self.assertIsNone(await self.store.get_credential(self.user["id"], "groq"))
        self.assertEqual((await self.client.get("/v1/credentials")).json()["credentials"], [])

    async def test_unknown_provider_is_rejected(self):
        rejected = await self.client.post(
            "/v1/credentials", json={"provider": "definitely-not-a-provider", "api_key": "x"}
        )
        self.assertEqual(rejected.status_code, 400)

    async def test_every_route_is_503_without_the_secret(self):
        self.deps._settings = replace(self.deps._settings, sentient_secret_key=None)
        post = await self.client.post(
            "/v1/credentials", json={"provider": "openai", "api_key": "sk-1234"}
        )
        self.assertEqual(post.status_code, 503)
        self.assertEqual((await self.client.get("/v1/credentials")).status_code, 503)
        self.assertEqual((await self.client.delete("/v1/credentials/openai")).status_code, 503)

    async def test_writing_a_credential_invalidates_the_users_cached_contexts(self):
        project = await self.store.create_project(self.user["id"], "P")
        await self.store.upsert_project_config(project["id"], llm_provider="openai")
        resolve_args = dict(user_id=self.user["id"], user_key="default", project_id=project["id"])
        cold = await self.deps.runtime_cache.resolve(
            self.store, self.deps._settings, **resolve_args
        )

        await self.client.post(
            "/v1/credentials", json={"provider": "openai", "api_key": "sk-fresh-9999"}
        )

        # Without invalidation the 60s TTL would keep serving `cold` with the env key.
        warm = await self.deps.runtime_cache.resolve(
            self.store, self.deps._settings, **resolve_args
        )
        self.assertEqual(warm.llm_settings["api_key"], "sk-fresh-9999")
        self.assertNotEqual(warm.config_signature, cold.config_signature)


if __name__ == "__main__":
    unittest.main()
