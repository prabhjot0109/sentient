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
        from logic.config import load_rag_settings
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


if __name__ == "__main__":
    unittest.main()
