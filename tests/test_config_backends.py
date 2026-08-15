from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from sentient.core.config import load_rag_settings


class BackendSettingsDefaultsTests(unittest.TestCase):
    def test_defaults_preserve_faiss_and_flags_off(self):
        with patch.dict(os.environ, {}, clear=False):
            for key in ("VECTOR_BACKEND", "QDRANT_URL", "RAG_CONDENSE_QUERIES", "RAG_HYBRID"):
                os.environ.pop(key, None)
            settings = load_rag_settings()
        self.assertEqual(settings.vector_backend, "faiss")
        self.assertIsNone(settings.qdrant_url)
        self.assertFalse(settings.condense_queries)
        self.assertFalse(settings.hybrid)
        self.assertEqual(settings.sparse_model, "Qdrant/bm25")
        self.assertEqual(settings.qdrant_collection, "sentient_lore")

    def test_env_overrides_are_parsed(self):
        with patch.dict(
            os.environ,
            {
                "VECTOR_BACKEND": "qdrant",
                "QDRANT_URL": "https://x.cloud.qdrant.io:6333",
                "QDRANT_API_KEY": "qk",
                "QDRANT_PREFER_GRPC": "true",
                "QDRANT_COLLECTION": "my_lore",
                "RAG_SPARSE_MODEL": "Qdrant/bm25",
                "RAG_CONDENSE_QUERIES": "true",
                "RAG_HYBRID": "true",
            },
            clear=False,
        ):
            settings = load_rag_settings()
        self.assertEqual(settings.vector_backend, "qdrant")
        self.assertEqual(settings.qdrant_url, "https://x.cloud.qdrant.io:6333")
        self.assertTrue(settings.qdrant_prefer_grpc)
        self.assertTrue(settings.condense_queries)
        self.assertTrue(settings.hybrid)

    def test_unknown_vector_backend_falls_back_to_faiss(self):
        with patch.dict(os.environ, {"VECTOR_BACKEND": "pinecone"}, clear=False):
            settings = load_rag_settings()
        self.assertEqual(settings.vector_backend, "faiss")


class CorsOriginSettingsTests(unittest.TestCase):
    def test_unset_means_no_extra_origins(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CORS_ALLOW_ORIGINS", None)
            self.assertEqual(load_rag_settings().cors_allow_origins, ())

    def test_comma_separated_origins_are_parsed_and_trimmed(self):
        with patch.dict(
            os.environ,
            {"CORS_ALLOW_ORIGINS": "https://app.example.com, https://sentient.gg "},
        ):
            self.assertEqual(
                load_rag_settings().cors_allow_origins,
                ("https://app.example.com", "https://sentient.gg"),
            )

    def test_empty_and_whitespace_entries_are_dropped(self):
        with patch.dict(os.environ, {"CORS_ALLOW_ORIGINS": " , ,https://a.dev, "}):
            # A trailing comma in .env must not turn into an empty allowed origin.
            self.assertEqual(load_rag_settings().cors_allow_origins, ("https://a.dev",))


if __name__ == "__main__":
    unittest.main()
