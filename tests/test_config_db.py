from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from sentient.core.config import load_rag_settings


class DbBackendConfigTests(unittest.TestCase):
    def test_defaults_to_sqlite_without_database_url(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = load_rag_settings()
        self.assertEqual(settings.db_backend, "sqlite")

    def test_defaults_to_neon_when_database_url_present(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgres://x"}, clear=True):
            settings = load_rag_settings()
        self.assertEqual(settings.db_backend, "neon")
        self.assertEqual(settings.database_url, "postgres://x")

    def test_explicit_db_backend_wins(self):
        with patch.dict(
            os.environ, {"DB_BACKEND": "supabase", "SUPABASE_DB_URL": "postgres://s"}, clear=True
        ):
            settings = load_rag_settings()
        self.assertEqual(settings.db_backend, "supabase")
        self.assertEqual(settings.supabase_db_url, "postgres://s")


class NeonAuthIssuerResolutionTests(unittest.TestCase):
    """`neon env pull` writes NEON_AUTH_BASE_URL; config read only NEON_AUTH_ISSUER,
    which nothing set. PyJWT's _validate_iss returns early when issuer is None, so
    issuer verification was silently off while authentication was on.

    The origin-only expectation below is measured, not assumed. A real token minted
    by the dev-console branch on 2026-08-22 carried
    iss=https://<endpoint>.neonauth.<region>.aws.neon.tech -- no /neondb/auth path,
    even though Better Auth documents the JWT issuer as defaulting to the full base
    URL. See docs/superpowers/verification/2026-08-22-H2-issuer.md.
    """

    def test_explicit_issuer_wins(self):
        with patch.dict(
            os.environ,
            {
                "NEON_AUTH_ISSUER": "https://explicit.example",
                "NEON_AUTH_BASE_URL": "https://derived.example/neondb/auth",
            },
            clear=True,
        ):
            settings = load_rag_settings()
        self.assertEqual(settings.neon_auth_issuer, "https://explicit.example")

    def test_issuer_is_derived_from_the_base_url_origin(self):
        with patch.dict(
            os.environ,
            {"NEON_AUTH_BASE_URL": "https://ep-abc.neonauth.example/neondb/auth"},
            clear=True,
        ):
            settings = load_rag_settings()
        self.assertEqual(settings.neon_auth_issuer, "https://ep-abc.neonauth.example")

    def test_a_base_url_with_a_port_keeps_the_port(self):
        with patch.dict(
            os.environ, {"NEON_AUTH_BASE_URL": "http://localhost:3000/neondb/auth"}, clear=True
        ):
            settings = load_rag_settings()
        self.assertEqual(settings.neon_auth_issuer, "http://localhost:3000")

    def test_no_base_url_means_no_issuer(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = load_rag_settings()
        self.assertIsNone(settings.neon_auth_issuer)

    def test_an_unparseable_base_url_yields_no_issuer(self):
        with patch.dict(os.environ, {"NEON_AUTH_BASE_URL": "not-a-url"}, clear=True):
            settings = load_rag_settings()
        self.assertIsNone(settings.neon_auth_issuer)


if __name__ == "__main__":
    unittest.main()
