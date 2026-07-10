from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from logic.config import load_rag_settings


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
        with patch.dict(os.environ, {"DB_BACKEND": "supabase",
                                     "SUPABASE_DB_URL": "postgres://s"}, clear=True):
            settings = load_rag_settings()
        self.assertEqual(settings.db_backend, "supabase")
        self.assertEqual(settings.supabase_db_url, "postgres://s")


if __name__ == "__main__":
    unittest.main()
