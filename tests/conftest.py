from __future__ import annotations

import pytest

# Every environment variable that logic/config.py, logic/rag_engine.py or api.py
# read as configuration. Importing `api` runs logic.rag_engine's load_dotenv() at
# import time, so a populated .env leaks the developer's real provider/RAG config
# into os.environ before any test runs — which silently flips provider resolution
# (LLM_PROVIDER=cerebras) and filters out FAISS hits (RAG_SCORE_THRESHOLD=0.2).
# Scrub them so every test starts from the same "fresh clone, no .env" baseline and
# opts into exactly the vars it sets via patch.dict.
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
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SENTIENT_SECRET_KEY",
    "CORS_ALLOW_ORIGINS",
    "TESSERACT_CMD",
)


@pytest.fixture(autouse=True)
def _isolate_config_env(monkeypatch):
    """Remove all config env vars before each test so a developer's .env can't
    leak into the suite. monkeypatch restores the original values afterwards."""
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    for name in _CONFIG_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
