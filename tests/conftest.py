from __future__ import annotations

import asyncio
import os

import pytest

# Every environment variable that core/config.py, services/rag.py or the api
# package read as configuration. Importing `api` runs load_dotenv() at
# import time, so a populated .env leaks the developer's real provider/RAG config
# into os.environ before any test runs — which silently flips provider resolution
# (LLM_PROVIDER=cerebras) and filters out FAISS hits (RAG_SCORE_THRESHOLD=0.2).
# Scrub them so every test starts from the same "fresh clone, no .env" baseline and
# opts into exactly the vars it sets via patch.dict.
#
# The auth and database names below are load-bearing for the same reason and were
# missing until 2026-08-22: a real NEON_AUTH_JWKS_URL in .env turned auth on for
# the whole suite (18 failures, all 401), and a real DATABASE_URL swapped
# SQLiteStateStore for a live Neon connection. Neither shows up in CI, which has
# no .env, so the suite was green there and red on the machine that could fix it.
# test_env_isolation.py pins the list against config.py so it cannot drift again.
_CONFIG_ENV_VARS = (
    "DATA_DIR",
    "FAISS_INDEX_PATH",
    "LLM_PROVIDER",
    "EMBEDDING_PROVIDER",
    "MODEL_NAME",
    "EMBEDDING_MODEL_NAME",
    "GOOGLE_API_KEY",
    "GROQ_API_KEY",
    "CEREBRAS_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "HUGGINGFACEHUB_API_TOKEN",
    "HF_TOKEN",
    "OPENAI_BASE_URL",
    "CEREBRAS_BASE_URL",
    "OPENROUTER_BASE_URL",
    "OPENAI_TIMEOUT_SECONDS",
    "GROQ_REASONING_EFFORT",
    "GROQ_REASONING_FORMAT",
    "RAG_CHUNK_SIZE",
    "RAG_CHUNK_OVERLAP",
    "RAG_TOP_K",
    "RAG_FETCH_K",
    "RAG_MMR_LAMBDA",
    "RAG_SEARCH_TYPE",
    "RAG_SCORE_THRESHOLD",
    "RAG_CONDENSE_QUERIES",
    "RAG_HYBRID",
    "RAG_SPARSE_MODEL",
    "VECTOR_BACKEND",
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "QDRANT_PREFER_GRPC",
    "QDRANT_COLLECTION",
    "SENTIENT_SECRET_KEY",
    "SENTIENT_SECRET_KEY_OLD",
    "CORS_ALLOW_ORIGINS",
    "TESSERACT_CMD",
    "DATABASE_URL",
    "DB_BACKEND",
    "SUPABASE_DB_URL",
    "NEON_AUTH_JWKS_URL",
    "NEON_AUTH_ISSUER",
    "NEON_AUTH_BASE_URL",
    "NEON_AUTH_ALGORITHMS",
    "LOG_LEVEL",
    "LOG_FORMAT",
    "UPLOAD_MAX_BYTES",
    "UPLOAD_USER_QUOTA_BYTES",
    "EXTRACT_MAX_CHARS",
    "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_COMPLETIONS_PER_MINUTE",
    "RATE_LIMIT_UPLOADS_PER_HOUR",
    "RATE_LIMIT_DEFAULT_PER_MINUTE",
    "TOKEN_QUOTA_PER_MONTH",
    "MAX_API_KEYS_PER_USER",
)


# Scrubbed here, at conftest import, and not only in the fixture below. pytest
# imports every test module during collection, before the first fixture runs, so
# a module-level `from sentient.api import deps` (test_rag_pipeline.py has one)
# executes `load_rag_settings()` against the developer's real .env and freezes the
# result in `deps._settings` for the whole session. Per-test scrubbing is too late
# to stop that; the fixture below only keeps each test honest afterwards.
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
for _name in _CONFIG_ENV_VARS:
    os.environ.pop(_name, None)


@pytest.fixture(autouse=True)
def _isolate_config_env(monkeypatch):
    """Remove all config env vars before each test so a developer's .env can't
    leak into the suite. monkeypatch restores the original values afterwards."""
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    for name in _CONFIG_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


async def drain_deferred() -> None:
    """Await every task `defer()` currently has in flight.

    G4's turn writer runs *after* the response, so a test that asserts on what it
    wrote — or that deletes the database directory in teardown — has to wait for
    it. Sleeping is the alternative and it is a race: on Windows the tempdir
    cleanup raises WinError 32 while the deferred write still holds state.db open.
    Loops because a drained task may itself have deferred more work.
    """
    while True:
        pending = [
            task
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task()
            and task.get_name().startswith("sentient-deferred-")
        ]
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)
