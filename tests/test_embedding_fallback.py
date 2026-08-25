from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sentient.adapters.state.sqlite_store import SQLiteStateStore
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
        from sentient.api import deps
        from sentient.services.runtime import RuntimeContext

        ctx = RuntimeContext(
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


class ProjectOverlayProviderPairTests(unittest.IsolatedAsyncioTestCase):
    """The overlay in services/runtime.py must honour the same invariant
    load_rag_settings does: never carry a provider and a model name that belong to
    different services.

    project_configs stores the provider and the model as two independent nullable
    columns, and the overlay applied them independently. A project that switched
    only `embedding_provider` therefore kept the env default's model -- a Google
    model id handed to sentence-transformers, which raises OSError inside
    run_reindex_job and leaves the project pinned at `reindexing_required`, where
    every retrieval 409s and nothing tells the user why. Measured against a live
    server on 2026-08-25 (V3 gate).
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SQLiteStateStore(str(Path(self.tmp.name) / "s.db"))
        with patch.dict(
            os.environ,
            {
                "GOOGLE_API_KEY": "AIza-test",
                "EMBEDDING_PROVIDER": "google",
                "EMBEDDING_MODEL_NAME": "models/gemini-embedding-001",
                "LLM_PROVIDER": "google",
                "MODEL_NAME": "gemini-2.5-flash",
            },
            clear=False,
        ):
            self.settings = load_rag_settings()

    def tearDown(self):
        self.tmp.cleanup()

    async def _context(self, **config):
        from sentient.services.runtime import resolve_runtime_context

        user = await self.store.ensure_user("A")
        proj = await self.store.create_project(user["id"], "P", base_preset="skyrim")
        await self.store.upsert_project_config(proj["id"], **config)
        return await resolve_runtime_context(
            self.store, self.settings, user_id=user["id"], user_key="uk", project_id=proj["id"]
        )

    async def test_switching_embedding_provider_alone_takes_that_providers_model(self):
        ctx = await self._context(embedding_provider="huggingface")

        self.assertEqual(ctx.rag_settings["embedding_provider"], "huggingface")
        self.assertEqual(ctx.rag_settings["embedding_model"], "BAAI/bge-base-en-v1.5")

    async def test_an_explicit_embedding_model_still_wins(self):
        ctx = await self._context(
            embedding_provider="huggingface",
            embedding_model_name="sentence-transformers/all-MiniLM-L6-v2",
        )

        self.assertEqual(
            ctx.rag_settings["embedding_model"], "sentence-transformers/all-MiniLM-L6-v2"
        )

    async def test_switching_llm_provider_alone_takes_that_providers_model(self):
        ctx = await self._context(llm_provider="groq")

        self.assertEqual(ctx.llm_settings["provider"], "groq")
        self.assertEqual(ctx.llm_settings["model"], "llama-3.3-70b-versatile")

    async def test_an_unchanged_provider_keeps_the_env_model(self):
        ctx = await self._context(rag_top_k=7)

        self.assertEqual(ctx.rag_settings["embedding_model"], "models/gemini-embedding-001")
        self.assertEqual(ctx.llm_settings["model"], "gemini-2.5-flash")
