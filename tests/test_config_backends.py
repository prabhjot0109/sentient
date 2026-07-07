from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from logic.config import load_rag_settings


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
                "VECTOR_BACKEND": "qdrant", "QDRANT_URL": "https://x.cloud.qdrant.io:6333",
                "QDRANT_API_KEY": "qk", "QDRANT_PREFER_GRPC": "true",
                "QDRANT_COLLECTION": "my_lore", "RAG_SPARSE_MODEL": "Qdrant/bm25",
                "RAG_CONDENSE_QUERIES": "true", "RAG_HYBRID": "true",
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


if __name__ == "__main__":
    unittest.main()
