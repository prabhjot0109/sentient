from __future__ import annotations

import hashlib
import unittest

from sentient.adapters.auth import generate_api_key, hash_key, user_key_of


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


class JwtVerificationTests(unittest.TestCase):
    def setUp(self):
        # _jwks_client is lru_cached (one PyJWKClient per URL in prod); clear it so
        # tests sharing a JWKS URL don't reuse a previous test's patched signing key.
        from sentient.adapters.auth import _jwks_client

        _jwks_client.cache_clear()

    def _settings(self, **over):
        from sentient.core.config import load_rag_settings

        s = load_rag_settings()
        return s.__class__(**{**s.__dict__, **over})

    def test_auth_disabled_without_jwks_url(self):
        from sentient.adapters.auth import auth_enabled

        self.assertFalse(auth_enabled(self._settings(neon_auth_jwks_url=None)))

    def test_verify_valid_rs256_token(self):
        from unittest.mock import patch

        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa

        from sentient.adapters.auth import verify_jwt

        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = jwt.encode(
            {"sub": "user-123", "iss": "https://neon.example"},
            priv,
            algorithm="RS256",
            headers={"kid": "k1"},
        )
        settings = self._settings(
            neon_auth_jwks_url="https://neon.example/jwks",
            neon_auth_issuer="https://neon.example",
            neon_auth_algorithms=["RS256"],
        )

        class _FakeSigningKey:
            key = priv.public_key()

        with patch("sentient.adapters.auth.jwt.PyJWKClient") as MockClient:
            MockClient.return_value.get_signing_key_from_jwt.return_value = _FakeSigningKey()
            claims = verify_jwt(token, settings)
        self.assertEqual(claims["sub"], "user-123")

    def test_verify_rejects_bad_issuer(self):
        from unittest.mock import patch

        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa

        from sentient.adapters.auth import AuthError, verify_jwt

        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = jwt.encode(
            {"sub": "u", "iss": "https://evil.example"},
            priv,
            algorithm="RS256",
            headers={"kid": "k1"},
        )
        settings = self._settings(
            neon_auth_jwks_url="https://neon.example/jwks",
            neon_auth_issuer="https://neon.example",
            neon_auth_algorithms=["RS256"],
        )

        class _FakeSigningKey:
            key = priv.public_key()

        with patch("sentient.adapters.auth.jwt.PyJWKClient") as MockClient:
            MockClient.return_value.get_signing_key_from_jwt.return_value = _FakeSigningKey()
            with self.assertRaises(AuthError):
                verify_jwt(token, settings)

    def test_a_token_minted_a_moment_in_the_future_is_accepted(self):
        """Neon's auth host clock leads the API host's. Measured 2026-08-22 against
        the dev-console branch: the auth server ran 2-3s ahead, and 14 of 14 freshly
        minted tokens carried an `iat` 0.7-1.5s in the future. PyJWT rejects those
        with ImmatureSignatureError unless given leeway, so every sign-in 401'd on a
        message that names neither auth nor clocks.

        Two independent hosts are never exactly in step, so this is a property of the
        deployment rather than a glitch to wait out. See
        docs/superpowers/verification/2026-08-22-H1-V2-results.md.
        """
        import time
        from unittest.mock import patch

        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa

        from sentient.adapters.auth import verify_jwt

        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = int(time.time())
        token = jwt.encode(
            {
                "sub": "u",
                "iss": "https://neon.example",
                "iat": now + 5,
                "exp": now + 900,
            },
            priv,
            algorithm="RS256",
            headers={"kid": "k1"},
        )
        settings = self._settings(
            neon_auth_jwks_url="https://neon.example/jwks",
            neon_auth_issuer="https://neon.example",
            neon_auth_algorithms=["RS256"],
        )

        class _FakeSigningKey:
            key = priv.public_key()

        with patch("sentient.adapters.auth.jwt.PyJWKClient") as MockClient:
            MockClient.return_value.get_signing_key_from_jwt.return_value = _FakeSigningKey()
            self.assertEqual(verify_jwt(token, settings)["sub"], "u")

    def test_a_long_expired_token_is_still_rejected(self):
        """The leeway above must not become an open door: it tolerates seconds of
        clock skew, not an expired session."""
        import time
        from unittest.mock import patch

        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa

        from sentient.adapters.auth import AuthError, verify_jwt

        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = int(time.time())
        token = jwt.encode(
            {"sub": "u", "iss": "https://neon.example", "iat": now - 3600, "exp": now - 600},
            priv,
            algorithm="RS256",
            headers={"kid": "k1"},
        )
        settings = self._settings(
            neon_auth_jwks_url="https://neon.example/jwks",
            neon_auth_issuer="https://neon.example",
            neon_auth_algorithms=["RS256"],
        )

        class _FakeSigningKey:
            key = priv.public_key()

        with patch("sentient.adapters.auth.jwt.PyJWKClient") as MockClient:
            MockClient.return_value.get_signing_key_from_jwt.return_value = _FakeSigningKey()
            with self.assertRaises(AuthError):
                verify_jwt(token, settings)

    def test_a_none_issuer_accepts_any_issuer(self):
        """Pins the fail-open this project shipped with, so the config-side fix has a
        reason a reader can check. `test_verify_rejects_bad_issuer` above sets the
        issuer explicitly, so it passed even while nothing in production ever set one.

        PyJWT's _validate_iss returns early when `issuer` is None: no error, no log
        line, and a token minted by anyone whose key the JWKS endpoint serves is
        accepted. `_resolve_neon_auth_issuer` is what keeps this path unreachable.
        """
        from unittest.mock import patch

        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa

        from sentient.adapters.auth import verify_jwt

        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = jwt.encode(
            {"sub": "u", "iss": "https://attacker.example"},
            priv,
            algorithm="RS256",
            headers={"kid": "k1"},
        )
        settings = self._settings(
            neon_auth_jwks_url="https://neon.example/jwks",
            neon_auth_issuer=None,
            neon_auth_algorithms=["RS256"],
        )

        class _FakeSigningKey:
            key = priv.public_key()

        with patch("sentient.adapters.auth.jwt.PyJWKClient") as MockClient:
            MockClient.return_value.get_signing_key_from_jwt.return_value = _FakeSigningKey()
            self.assertEqual(verify_jwt(token, settings)["sub"], "u")


class ResolveUserTests(unittest.IsolatedAsyncioTestCase):
    def _settings(self, **over):
        from sentient.core.config import load_rag_settings

        s = load_rag_settings()
        return s.__class__(**{**s.__dict__, **over})

    async def _store(self):
        import tempfile
        from pathlib import Path

        from sentient.adapters.state.sqlite_store import SQLiteStateStore

        self._tmp = tempfile.TemporaryDirectory()
        return SQLiteStateStore(str(Path(self._tmp.name) / "s.db"))

    async def test_default_user_when_no_auth(self):
        from sentient.adapters.auth import resolve_user

        store = await self._store()
        uid, uk = await resolve_user(store, self._settings(neon_auth_jwks_url=None))
        self.assertEqual(uk, "default")
        self.assertTrue(uid)

    async def test_api_key_resolves_owner_and_caches(self):
        from sentient.adapters.auth import IdentityCache, hash_key, resolve_user

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
        from sentient.adapters.auth import AuthError, resolve_user

        store = await self._store()
        with self.assertRaises(AuthError):
            await resolve_user(
                store, self._settings(neon_auth_jwks_url=None), api_key="sk-sent-nope"
            )

    async def test_identity_cache_can_be_cleared_after_key_revocation(self):
        from sentient.adapters.auth import AuthError, IdentityCache, hash_key, resolve_user

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
