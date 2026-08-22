from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, cast
from urllib.parse import urlsplit

Provider = Literal["google", "openai", "huggingface", "groq", "cerebras", "openrouter"]

# Providers that speak the OpenAI chat-completions wire format, so they can all
# be driven by ChatOpenAI with just a provider-specific base URL and key.
OPENAI_COMPATIBLE = {"openai", "cerebras", "openrouter"}

# Chat-only providers with no embeddings API. If one of these is auto-selected
# for embeddings, we fall back to local HuggingFace embeddings (no key needed).
LLM_ONLY_PROVIDERS = {"groq", "cerebras", "openrouter"}
SearchType = Literal["mmr", "similarity"]


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


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_neon_auth_issuer() -> str | None:
    """The `iss` claim tokens are compared against, or None to skip the check.

    `neon env pull` writes NEON_AUTH_BASE_URL; this function used to read only
    NEON_AUTH_ISSUER, which nothing set. PyJWT's _validate_iss returns early when
    issuer is None, so issuer verification was silently off while authentication
    was on -- no error, no log line.

    Origin-only is measured, not inherited from a doc. Better Auth documents the
    JWT issuer as defaulting to the full base URL, but a real token from the
    dev-console branch carries the origin with no /neondb/auth path. Since
    jwt.decode(issuer=...) is an exact string compare, taking Better Auth at its
    word here would have rejected every valid token. An explicit NEON_AUTH_ISSUER
    still wins, because the value is branch-specific and a future Neon change
    must be overridable without a release.
    """
    explicit = os.getenv("NEON_AUTH_ISSUER")
    if explicit:
        return explicit
    parts = urlsplit(os.getenv("NEON_AUTH_BASE_URL") or "")
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"


def _resolve_db_backend() -> str:
    explicit = (os.getenv("DB_BACKEND") or "").strip().lower()
    if explicit in {"neon", "supabase", "sqlite"}:
        return explicit
    return "neon" if os.getenv("DATABASE_URL") else "sqlite"


def _normalize_vector_backend(value: str | None) -> str:
    normalized = (value or "faiss").strip().lower()
    return normalized if normalized in {"faiss", "qdrant"} else "faiss"


def _normalize_provider(value: str | None, *, default: str = "auto") -> str:
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {
        "google",
        "openai",
        "huggingface",
        "groq",
        "cerebras",
        "openrouter",
        "auto",
    }:
        return normalized
    return default


def _normalize_search_type(value: str | None) -> SearchType:
    normalized = (value or "similarity").strip().lower()
    if normalized in {"mmr", "similarity"}:
        return normalized  # type: ignore[return-value]
    return "similarity"


def resolve_provider(
    preferred: str | None,
    *,
    api_key: str | None,
    fallback: Provider,
) -> Provider:
    normalized = _normalize_provider(preferred)

    if normalized != "auto":
        return normalized  # type: ignore[return-value]

    if api_key:
        if api_key.startswith("AIza"):
            return "google"
        if api_key.startswith("hf_"):
            return "huggingface"
        if api_key.startswith("gsk_"):
            return "groq"
        # OpenRouter keys are "sk-or-..." — check before the generic "sk-"
        # OpenAI fallback so they aren't mistaken for OpenAI keys.
        if api_key.startswith("sk-or-"):
            return "openrouter"
        if api_key.startswith("csk-"):
            return "cerebras"
        return "openai"

    if os.getenv("GOOGLE_API_KEY"):
        return "google"

    if os.getenv("GROQ_API_KEY"):
        return "groq"

    if os.getenv("CEREBRAS_API_KEY"):
        return "cerebras"

    if os.getenv("OPENROUTER_API_KEY"):
        return "openrouter"

    if os.getenv("OPENAI_API_KEY"):
        return "openai"

    if os.getenv("HUGGINGFACEHUB_API_TOKEN") or os.getenv("HF_TOKEN"):
        return "huggingface"

    return fallback


def _provider_env_key(provider: str) -> str | None:
    """The API key from the environment that belongs to `provider`."""
    if provider == "google":
        return os.getenv("GOOGLE_API_KEY")
    if provider == "groq":
        return os.getenv("GROQ_API_KEY")
    if provider == "cerebras":
        return os.getenv("CEREBRAS_API_KEY")
    if provider == "openrouter":
        return os.getenv("OPENROUTER_API_KEY")
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY")
    if provider == "huggingface":
        return os.getenv("HUGGINGFACEHUB_API_TOKEN") or os.getenv("HF_TOKEN")
    return None


def provider_api_key(provider: str, override: str | None) -> str | None:
    """Pick the right key for `provider`, allowing multiple keys to coexist.

    A client-supplied `override` is only used when it actually belongs to this
    provider (detected by key prefix); otherwise we fall back to the provider's
    own env var. This is what lets, e.g., a Google key drive embeddings while a
    Groq key drives the LLM in the same process.
    """
    # `provider` is a plain str because one caller passes a project-config column,
    # which is not statically known to be a valid Provider. resolve_provider tolerates
    # an unknown fallback (it hands it straight back), so the cast is safe.
    if (
        override
        and resolve_provider("auto", api_key=override, fallback=cast(Provider, provider))
        == provider
    ):
        return override
    return _provider_env_key(provider)


def provider_base_url(provider: str) -> str | None:
    """OpenAI-compatible providers need a base URL; native SDKs don't."""
    if provider == "openai":
        return os.getenv("OPENAI_BASE_URL")
    if provider == "cerebras":
        return os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")
    if provider == "openrouter":
        return os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    return None


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
    score_threshold: float
    request_timeout: float
    db_backend: str
    database_url: str | None
    supabase_db_url: str | None
    vector_backend: str
    qdrant_url: str | None
    qdrant_api_key: str | None
    qdrant_prefer_grpc: bool
    qdrant_collection: str
    sparse_model: str
    condense_queries: bool
    hybrid: bool
    neon_auth_jwks_url: str | None
    neon_auth_issuer: str | None
    neon_auth_algorithms: list[str]
    sentient_secret_key: str | None
    # Deployed browser origins allowed to call the API. A tuple, not a list, so
    # RAGSettings stays hashable/frozen like every other field here.
    cors_allow_origins: tuple[str, ...]
    log_level: str
    log_format: str


def load_rag_settings(api_key: str | None = None) -> RAGSettings:
    data_dir = os.getenv("DATA_DIR", "data")
    index_path = os.getenv("FAISS_INDEX_PATH", os.path.join(data_dir, "faiss_index"))

    llm_provider = resolve_provider(
        os.getenv("LLM_PROVIDER"),
        api_key=api_key,
        fallback="huggingface",
    )
    llm_api_key = provider_api_key(llm_provider, api_key)
    llm_model = os.getenv(
        "MODEL_NAME",
        {
            "google": "gemini-2.5-flash",
            "openai": "gpt-4o-mini",
            "huggingface": "Qwen/Qwen2.5-7B-Instruct",
            # Groq's fastest non-reasoning chat model — no "thinking" pass, so
            # replies come back immediately, which is what the NPC path wants.
            "groq": "llama-3.3-70b-versatile",
            "cerebras": "llama-3.3-70b",
            "openrouter": "meta-llama/llama-3.3-70b-instruct",
        }[llm_provider],
    )
    llm_base_url = provider_base_url(llm_provider)

    embedding_provider = resolve_provider(
        os.getenv("EMBEDDING_PROVIDER"),
        api_key=api_key,
        fallback="huggingface",
    )
    # Groq/Cerebras/OpenRouter serve chat models only — no embeddings API. If one
    # auto-resolved for embeddings (e.g. only that provider's key is set), fall
    # back to local HuggingFace embeddings, which need no key.
    embedding_fallback = embedding_provider in LLM_ONLY_PROVIDERS
    if embedding_fallback:
        embedding_provider = "huggingface"
    embedding_api_key = provider_api_key(embedding_provider, api_key)
    # EMBEDDING_MODEL_NAME names a model on the provider it was configured for. Once
    # the fallback above has replaced that provider, the name no longer belongs to
    # anything — honouring it asks HuggingFace to load e.g. a Google model from the
    # Hub, which fails. Settings must never carry a provider/model pair that
    # disagree, so the fallback takes the model with it.
    embedding_model_override = None if embedding_fallback else os.getenv("EMBEDDING_MODEL_NAME")
    embedding_model = (
        embedding_model_override
        or {
            "google": "models/gemini-embedding-001",
            "openai": "text-embedding-3-small",
            "huggingface": "BAAI/bge-base-en-v1.5",
        }[embedding_provider]
    )
    embedding_base_url = provider_base_url(embedding_provider)

    chunk_size = _env_int("RAG_CHUNK_SIZE", 900)
    chunk_overlap = min(_env_int("RAG_CHUNK_OVERLAP", 150, minimum=0), chunk_size - 1)
    top_k = _env_int("RAG_TOP_K", 4)
    fetch_k = _env_int("RAG_FETCH_K", max(top_k * 3, top_k))
    request_timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))

    vector_backend = _normalize_vector_backend(os.getenv("VECTOR_BACKEND"))
    qdrant_url = os.getenv("QDRANT_URL") or None
    qdrant_api_key = os.getenv("QDRANT_API_KEY") or None
    qdrant_prefer_grpc = _env_bool("QDRANT_PREFER_GRPC", False)
    qdrant_collection = os.getenv("QDRANT_COLLECTION", "sentient_lore")
    sparse_model = os.getenv("RAG_SPARSE_MODEL", "Qdrant/bm25")
    condense_queries = _env_bool("RAG_CONDENSE_QUERIES", False)
    hybrid = _env_bool("RAG_HYBRID", False)

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
        score_threshold=_env_float("RAG_SCORE_THRESHOLD", 0.0),
        request_timeout=request_timeout,
        db_backend=_resolve_db_backend(),
        database_url=os.getenv("DATABASE_URL"),
        supabase_db_url=os.getenv("SUPABASE_DB_URL"),
        vector_backend=vector_backend,
        qdrant_url=qdrant_url,
        qdrant_api_key=qdrant_api_key,
        qdrant_prefer_grpc=qdrant_prefer_grpc,
        qdrant_collection=qdrant_collection,
        sparse_model=sparse_model,
        condense_queries=condense_queries,
        hybrid=hybrid,
        neon_auth_jwks_url=os.getenv("NEON_AUTH_JWKS_URL"),
        neon_auth_issuer=_resolve_neon_auth_issuer(),
        neon_auth_algorithms=[
            a.strip()
            for a in os.getenv("NEON_AUTH_ALGORITHMS", "EdDSA,RS256").split(",")
            if a.strip()
        ],
        sentient_secret_key=os.getenv("SENTIENT_SECRET_KEY") or None,
        cors_allow_origins=tuple(
            origin.strip()
            for origin in (os.getenv("CORS_ALLOW_ORIGINS") or "").split(",")
            if origin.strip()
        ),
        log_level=(os.getenv("LOG_LEVEL") or "INFO").upper(),
        # Anything that is not exactly "json" is text. A typo should degrade to a
        # readable console, never to a format no log shipper can parse.
        log_format="json" if (os.getenv("LOG_FORMAT") or "text").lower() == "json" else "text",
    )
