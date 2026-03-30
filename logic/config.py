from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal


Provider = Literal["openrouter", "openai", "huggingface"]
SearchType = Literal["mmr", "similarity"]

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default

    try:
        value = int(raw)
    except ValueError:
        return default

    return max(value, minimum)


def _env_float(
    name: str,
    default: float,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default

    try:
        value = float(raw)
    except ValueError:
        return default

    return min(max(value, minimum), maximum)


def _normalize_provider(value: str | None, *, default: str = "auto") -> str:
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"openrouter", "openai", "huggingface", "auto"}:
        return normalized
    return default


def _normalize_search_type(value: str | None) -> SearchType:
    normalized = (value or "mmr").strip().lower()
    if normalized in {"mmr", "similarity"}:
        return normalized  # type: ignore[return-value]
    return "mmr"


def is_openrouter_key(api_key: str | None) -> bool:
    return bool(api_key and api_key.startswith("sk-or-"))


def resolve_provider(
    preferred: str | None,
    *,
    api_key: str | None,
    fallback: Provider,
) -> Provider:
    normalized = _normalize_provider(preferred)

    if normalized != "auto":
        return normalized  # type: ignore[return-value]

    if is_openrouter_key(api_key):
        return "openrouter"

    if api_key:
        return "openai"

    if os.getenv("OPENROUTER_API_KEY"):
        return "openrouter"

    if os.getenv("OPENAI_API_KEY"):
        return "openai"

    return fallback


@dataclass(frozen=True)
class RAGSettings:
    data_dir: str
    index_path: str
    llm_provider: Provider
    llm_model: str
    llm_api_key: str | None
    llm_base_url: str | None
    embedding_provider: Provider
    embedding_model: str
    embedding_api_key: str | None
    embedding_base_url: str | None
    chunk_size: int
    chunk_overlap: int
    top_k: int
    fetch_k: int
    lambda_mult: float
    search_type: SearchType
    request_timeout: float


def load_rag_settings(api_key: str | None = None) -> RAGSettings:
    data_dir = os.getenv("DATA_DIR", "data")
    index_path = os.getenv("FAISS_INDEX_PATH", os.path.join(data_dir, "faiss_index"))

    llm_provider = resolve_provider(
        os.getenv("LLM_PROVIDER"),
        api_key=api_key,
        fallback="openrouter",
    )
    llm_api_key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    llm_model = os.getenv(
        "MODEL_NAME",
        "openai/gpt-4o-mini" if llm_provider == "openrouter" else "gpt-4o-mini",
    )
    llm_base_url = (
        os.getenv("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL)
        if llm_provider == "openrouter"
        else os.getenv("OPENAI_BASE_URL")
    )

    embedding_provider = resolve_provider(
        os.getenv("EMBEDDING_PROVIDER"),
        api_key=api_key,
        fallback="huggingface",
    )
    embedding_api_key = (
        api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    )
    embedding_model = os.getenv(
        "EMBEDDING_MODEL_NAME",
        {
            "openrouter": "openai/text-embedding-3-small",
            "openai": "text-embedding-3-small",
            "huggingface": "BAAI/bge-base-en-v1.5",
        }[embedding_provider],
    )
    embedding_base_url = (
        os.getenv("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL)
        if embedding_provider == "openrouter"
        else os.getenv("OPENAI_BASE_URL")
    )

    chunk_size = _env_int("RAG_CHUNK_SIZE", 900)
    chunk_overlap = min(_env_int("RAG_CHUNK_OVERLAP", 150, minimum=0), chunk_size - 1)
    top_k = _env_int("RAG_TOP_K", 4)
    fetch_k = _env_int("RAG_FETCH_K", max(top_k * 3, top_k))
    request_timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))

    return RAGSettings(
        data_dir=data_dir,
        index_path=index_path,
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_api_key=embedding_api_key,
        embedding_base_url=embedding_base_url,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        top_k=top_k,
        fetch_k=fetch_k,
        lambda_mult=_env_float("RAG_MMR_LAMBDA", 0.65),
        search_type=_normalize_search_type(os.getenv("RAG_SEARCH_TYPE")),
        request_timeout=request_timeout,
    )
