from __future__ import annotations

import hashlib
import unittest

from logic.auth import generate_api_key, hash_key, user_key_of


class KeyPrimitiveTests(unittest.TestCase):
    def test_hash_key_is_sha256_hex(self):
        self.assertEqual(hash_key("abc"), hashlib.sha256(b"abc").hexdigest())

    def test_user_key_is_short_and_stable_and_opaque(self):
        uk = user_key_of("super-secret-key")
        self.assertEqual(len(uk), 16)
        self.assertNotIn("secret", uk)
        self.assertEqual(uk, user_key_of("super-secret-key"))

    def test_generate_api_key_prefixed_and_hash_matches(self):
        raw, h = generate_api_key()
        self.assertTrue(raw.startswith("sk-sent-"))
        self.assertEqual(h, hash_key(raw))
        raw2, _ = generate_api_key()
        self.assertNotEqual(raw, raw2)  # random


import unittest as _ut


class JwtVerificationTests(_ut.TestCase):
    def setUp(self):
        # _jwks_client is lru_cached (one PyJWKClient per URL in prod); clear it so
        # tests sharing a JWKS URL don't reuse a previous test's patched signing key.
        from logic.auth import _jwks_client
        _jwks_client.cache_clear()

    def _settings(self, **over):
        from sentient.core.config import load_rag_settings
        s = load_rag_settings()
        return s.__class__(**{**s.__dict__, **over})

    def test_auth_disabled_without_jwks_url(self):
        from logic.auth import auth_enabled
        self.assertFalse(auth_enabled(self._settings(neon_auth_jwks_url=None)))

    def test_verify_valid_rs256_token(self):
        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa
        from unittest.mock import patch
        from logic.auth import verify_jwt

        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = jwt.encode({"sub": "user-123", "iss": "https://neon.example"}, priv,
                           algorithm="RS256", headers={"kid": "k1"})
        settings = self._settings(neon_auth_jwks_url="https://neon.example/jwks",
                                  neon_auth_issuer="https://neon.example",
                                  neon_auth_algorithms=["RS256"])

        class _FakeSigningKey:
            key = priv.public_key()

        with patch("logic.auth.jwt.PyJWKClient") as MockClient:
            MockClient.return_value.get_signing_key_from_jwt.return_value = _FakeSigningKey()
            claims = verify_jwt(token, settings)
        self.assertEqual(claims["sub"], "user-123")

    def test_verify_rejects_bad_issuer(self):
        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa
        from unittest.mock import patch
        from logic.auth import verify_jwt, AuthError

        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = jwt.encode({"sub": "u", "iss": "https://evil.example"}, priv,
                           algorithm="RS256", headers={"kid": "k1"})
        settings = self._settings(neon_auth_jwks_url="https://neon.example/jwks",
                                  neon_auth_issuer="https://neon.example",
                                  neon_auth_algorithms=["RS256"])

        class _FakeSigningKey:
            key = priv.public_key()

        with patch("logic.auth.jwt.PyJWKClient") as MockClient:
            MockClient.return_value.get_signing_key_from_jwt.return_value = _FakeSigningKey()
            with self.assertRaises(AuthError):
                verify_jwt(token, settings)


class ResolveUserTests(_ut.IsolatedAsyncioTestCase):
    def _settings(self, **over):
        from sentient.core.config import load_rag_settings
        s = load_rag_settings()
        return s.__class__(**{**s.__dict__, **over})

    async def _store(self):
        import tempfile
        from pathlib import Path
        from logic.state.sqlite_store import SQLiteStateStore
        self._tmp = tempfile.TemporaryDirectory()
        return SQLiteStateStore(str(Path(self._tmp.name) / "s.db"))

    async def test_default_user_when_no_auth(self):
        from logic.auth import resolve_user
        store = await self._store()
        uid, uk = await resolve_user(store, self._settings(neon_auth_jwks_url=None))
        self.assertEqual(uk, "default")
        self.assertTrue(uid)

    async def test_api_key_resolves_owner_and_caches(self):
        from logic.auth import resolve_user, hash_key, IdentityCache
        store = await self._store()
        user = await store.ensure_user("owner-1")
        await store.create_api_key(user["id"], hash_key("sk-sent-abc"))
        cache = IdentityCache()
        calls = {"n": 0}
        orig = store.get_user_by_api_key_hash
        async def counting(h):
            calls["n"] += 1
            return await orig(h)
        store.get_user_by_api_key_hash = counting  # type: ignore
        s = self._settings(neon_auth_jwks_url=None)
        uid1, _ = await resolve_user(store, s, api_key="sk-sent-abc", cache=cache)
        uid2, _ = await resolve_user(store, s, api_key="sk-sent-abc", cache=cache)
        self.assertEqual(uid1, user["id"])
        self.assertEqual(uid2, user["id"])
        self.assertEqual(calls["n"], 1)  # second hit served from cache, no DB

    async def test_unknown_api_key_rejected(self):
        from logic.auth import resolve_user, AuthError
        store = await self._store()
        with self.assertRaises(AuthError):
            await resolve_user(store, self._settings(neon_auth_jwks_url=None), api_key="sk-sent-nope")

    async def test_identity_cache_can_be_cleared_after_key_revocation(self):
        from logic.auth import AuthError, IdentityCache, hash_key, resolve_user

        store = await self._store()
        user = await store.ensure_user("owner-1")
        await store.create_api_key(user["id"], hash_key("sk-sent-abc"))
        cache = IdentityCache()
        settings = self._settings(neon_auth_jwks_url=None)

        await resolve_user(store, settings, api_key="sk-sent-abc", cache=cache)
        row = (await store.list_api_keys(user["id"]))[0]
        await store.revoke_api_key(user["id"], row["id"])
        cache.clear()

        with self.assertRaises(AuthError):
            await resolve_user(store, settings, api_key="sk-sent-abc", cache=cache)


if __name__ == "__main__":
    unittest.main()
