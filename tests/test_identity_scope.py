"""Cross-surface tenant identity: one human is one tenant, however they signed in.

The suite could not express this class of bug before. Every existing auth test
authenticates one way and asserts within that one way, so a `user_key` derived
from the credential looked correct from every angle -- while lore uploaded in the
console stayed invisible to the game, which sends an API key. These tests
authenticate one way, then the other, and compare. Spec A1 / G1.
"""

from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from sentient.adapters.auth import generate_api_key, resolve_user, user_key_of
from sentient.core.config import load_rag_settings


class _FakeStore:
    """Minimal StateStore stand-in covering only what resolve_user calls."""

    def __init__(self) -> None:
        self.users: dict[str, dict] = {}
        self.keys: dict[str, dict] = {}

    async def ensure_user(self, external_auth_id, email=None):
        key = external_auth_id if external_auth_id is not None else "__default__"
        row = self.users.get(key)
        if row is None:
            row = {"id": f"uid-{len(self.users) + 1}", "external_auth_id": key, "email": email}
            self.users[key] = row
        return row

    async def get_user_by_api_key_hash(self, key_hash):
        return self.keys.get(key_hash)


class CrossSurfaceTenantTests(unittest.IsolatedAsyncioTestCase):
    def _settings(self, **over):
        return replace(load_rag_settings(), **over)

    async def test_jwt_and_api_key_for_one_user_resolve_to_one_tenant(self):
        store = _FakeStore()
        settings = self._settings(neon_auth_jwks_url="https://neon.example/jwks")
        user = await store.ensure_user("neon-sub-abc", "a@example.com")
        raw_key, key_hash = generate_api_key()
        store.keys[key_hash] = {"user_id": user["id"], "revoked": False}

        with patch(
            "sentient.adapters.auth.verify_jwt",
            return_value={"sub": "neon-sub-abc", "email": "a@example.com"},
        ):
            jwt_identity = await resolve_user(store, settings, jwt_token="tok")
        key_identity = await resolve_user(store, settings, api_key=raw_key)

        self.assertEqual(jwt_identity[0], key_identity[0])
        self.assertEqual(jwt_identity[1], key_identity[1])
        self.assertEqual(jwt_identity[1], user_key_of(user["id"]))

    async def test_two_api_keys_for_one_user_are_one_tenant(self):
        store = _FakeStore()
        settings = self._settings()
        user = await store.ensure_user("neon-sub-abc")
        first_raw, first_hash = generate_api_key()
        second_raw, second_hash = generate_api_key()
        store.keys[first_hash] = {"user_id": user["id"], "revoked": False}
        store.keys[second_hash] = {"user_id": user["id"], "revoked": False}

        first = await resolve_user(store, settings, api_key=first_raw)
        second = await resolve_user(store, settings, api_key=second_raw)

        self.assertEqual(first[1], second[1])

    async def test_two_different_users_stay_in_different_tenants(self):
        store = _FakeStore()
        settings = self._settings()
        alice = await store.ensure_user("sub-alice")
        bob = await store.ensure_user("sub-bob")
        alice_raw, alice_hash = generate_api_key()
        bob_raw, bob_hash = generate_api_key()
        store.keys[alice_hash] = {"user_id": alice["id"], "revoked": False}
        store.keys[bob_hash] = {"user_id": bob["id"], "revoked": False}

        self.assertNotEqual(
            (await resolve_user(store, settings, api_key=alice_raw))[1],
            (await resolve_user(store, settings, api_key=bob_raw))[1],
        )

    async def test_anonymous_still_resolves_to_the_legacy_default_partition(self):
        store = _FakeStore()
        _, user_key = await resolve_user(store, self._settings())
        self.assertEqual(user_key, "default")
