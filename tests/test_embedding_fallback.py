from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import patch

from sentient.core.config import load_rag_settings


class LLMOnlyProviderFallbackTests(unittest.TestCase):
    """Groq/Cerebras/OpenRouter serve no embeddings, so load_rag_settings falls back
    to local HuggingFace. The resulting settings must be internally coherent: a
    provider and a model name that belong to each other."""

    def test_fallback_replaces_the_model_name_too(self):
        with patch.dict(
            os.environ,
            {"EMBEDDING_MODEL_NAME": "models/gemini-embedding-001"},
            clear=False,
        ):
            settings = load_rag_settings("csk-cerebras-key")

        self.assertEqual(settings.llm_provider, "cerebras")
        self.assertEqual(settings.embedding_provider, "huggingface")
        # The env name targets the provider we just replaced; keeping it asks
        # HuggingFace to load a Google model from the Hub, which 404s.
        self.assertEqual(settings.embedding_model, "BAAI/bge-base-en-v1.5")

    def test_explicit_huggingface_still_honours_the_env_model(self):
        with patch.dict(
            os.environ,
            {
                "EMBEDDING_PROVIDER": "huggingface",
                "EMBEDDING_MODEL_NAME": "sentence-transformers/all-MiniLM-L6-v2",
            },
            clear=False,
        ):
            settings = load_rag_settings("csk-cerebras-key")

        self.assertEqual(settings.embedding_provider, "huggingface")
        self.assertEqual(settings.embedding_model, "sentence-transformers/all-MiniLM-L6-v2")

    def test_google_embeddings_are_untouched_when_no_fallback_fires(self):
        with patch.dict(
            os.environ,
            {
                "GOOGLE_API_KEY": "AIza-test",
                "EMBEDDING_MODEL_NAME": "models/gemini-embedding-001",
            },
            clear=False,
        ):
            settings = load_rag_settings()

        self.assertEqual(settings.embedding_provider, "google")
        self.assertEqual(settings.embedding_model, "models/gemini-embedding-001")


class BrainEmbeddingSpaceTests(unittest.TestCase):
    """/v1/chat resolved embeddings from the LLM key, while ingest, /health and the
    warmup resolved them from the environment. Two disagreeing paths means the brain
    can query an index built in a different embedding space."""

    def test_brain_uses_the_context_embedding_settings_not_the_llm_key(self):
        from sentient.api import app as api
        from sentient.api import deps

        ctx = api.RuntimeContext(
            user_key="default",
            user_id=None,
            project_id=None,
            session_id=None,
            llm_settings={
                "provider": "cerebras",
                "model": "llama-3.3-70b",
                "base_url": "https://api.cerebras.ai/v1",
                "api_key": "csk-cerebras-key",
                "timeout": 60.0,
            },
            rag_settings={
                "embedding_provider": "google",
                "embedding_model": "models/gemini-embedding-001",
                "embedding_api_key": "AIza-test",
                "mrl_vector_size": None,
                "search_type": "similarity",
                "top_k": 4,
                "fetch_k": 12,
                "mmr_lambda": 0.65,
                "score_threshold": 0.0,
                "chunk_size": 900,
                "chunk_overlap": 150,
            },
            system_prompt="",
            config_signature="sig",
        )

        captured: dict = {}

        def fake_brain(api_key=None, *, settings=None):
            captured["api_key"] = api_key
            captured["settings"] = settings
            return object()

        with patch.object(deps, "NPCBrain", fake_brain):
            asyncio.run(deps._build_brain_bundle(ctx))

        self.assertIsNotNone(captured["settings"], "the brain must be given resolved settings")
        self.assertEqual(captured["settings"].embedding_provider, "google")
        self.assertEqual(captured["settings"].embedding_model, "models/gemini-embedding-001")
        self.assertEqual(captured["settings"].embedding_api_key, "AIza-test")
        # The LLM half still comes from the context.
        self.assertEqual(captured["settings"].llm_provider, "cerebras")
        self.assertEqual(captured["settings"].llm_api_key, "csk-cerebras-key")


if __name__ == "__main__":
    unittest.main()
