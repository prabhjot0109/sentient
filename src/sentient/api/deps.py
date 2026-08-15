"""Process-wide singletons and the dependency builders every router shares.

**Import this module, never names out of it:**

```python
from sentient.api import deps          # deps.state_store resolves at call time
...
await deps.state_store.list_projects(user_id)

# NOT:
from sentient.api.deps import state_store   # binds at import; patching has no effect
```

`from X import Y` binds the value at import time. A router that imported the
name directly would keep using the real store while a test patched
`deps.state_store` and appeared to be using a fake -- a test passing for the
wrong reason, which is worse than a test failing. `import-linter` cannot see
this; `tests/test_layer_rule.py` pins it instead. Spec section 7.1.

The singletons stay module-level rather than becoming FastAPI `Depends` +
`app.dependency_overrides`. That conversion is more idiomatic and is a good
follow-up, but it changes the test suite during the one refactor whose entire
safety argument rests on the suite being untouched evidence. Spec section 7.2.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import Header, HTTPException

from sentient.adapters.auth import (
    AuthError,
    IdentityCache,
    auth_enabled,
    resolve_user,
)
from sentient.adapters.documents import ArchivesIngestion
from sentient.adapters.llm.models import build_chat_model
from sentient.adapters.state import get_state_store
from sentient.core.cache import ObjectRegistry
from sentient.core.concurrency import IngestJob, IngestQueue, ReindexJob, SessionLocks
from sentient.core.config import load_rag_settings, provider_base_url
from sentient.services import ingestion
from sentient.services.rag import NPCBrain
from sentient.services.runtime import (
    RuntimeCache,
    RuntimeContext,
    resolve_runtime_context,
)

# Runtime caches (not a global brain). Clients are built once per config_signature
# and reused; config/persona writes invalidate RuntimeCache for that project.
_settings = load_rag_settings()
state_store = get_state_store(_settings)
identity_cache = IdentityCache()
runtime_cache = RuntimeCache()
object_registry = ObjectRegistry()
session_locks = SessionLocks()

# Any of these being set means we have enough to operate; load_rag_settings then
# picks the right per-provider key, so multiple keys can coexist (e.g. Google for
# embeddings + Groq for the LLM).
_PROVIDER_KEY_ENV = (
    "GOOGLE_API_KEY",
    "GROQ_API_KEY",
    "CEREBRAS_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "HUGGINGFACEHUB_API_TOKEN",
    "HF_TOKEN",
)

# Provider keys that may appear in the URL path (Mantella-style). Product keys
# (`sk-sent-…`) are identity, never LLM credentials.
_PROVIDER_KEY_PREFIXES = ("AIza", "gsk_", "sk-", "csk-", "hf_")


def any_provider_key_present() -> bool:
    return any(os.getenv(name) for name in _PROVIDER_KEY_ENV)


def _as_provider_key(raw: str | None) -> str | None:
    """Return raw only when it looks like a provider credential, not a product key."""
    if not raw or raw.startswith("sk-sent-"):
        return None
    if raw.startswith(_PROVIDER_KEY_PREFIXES):
        return raw
    return None


async def build_llm(ctx: RuntimeContext):
    s = ctx.llm_settings
    return await asyncio.to_thread(
        build_chat_model,
        s["provider"],
        s["model"],
        s["base_url"],
        s["api_key"],
        s["timeout"],
    )


async def get_llm(ctx: RuntimeContext):
    return await object_registry.get(ctx.config_signature, lambda: build_llm(ctx))


def _archive_scope(ctx: RuntimeContext) -> str:
    """Return an opaque FAISS partition name for this runtime context.

    Qdrant applies the same identity at query time through payload filters. FAISS
    has no payload filtering, so it must use a physically separate index per
    user/project (while preserving the legacy env-default index for default
    requests).
    """
    if ctx.user_key == "default" and ctx.project_id is None:
        return "default"

    user = hashlib.sha256(ctx.user_key.encode("utf-8")).hexdigest()[:24]
    project = hashlib.sha256((ctx.project_id or "legacy").encode("utf-8")).hexdigest()[:24]
    return f"{user}-{project}"


def _archive_settings(ctx: RuntimeContext):
    """Overlay the context's LLM/RAG configuration onto process defaults."""
    llm = ctx.llm_settings
    rag = ctx.rag_settings
    embedding_provider = rag["embedding_provider"]
    return replace(
        _settings,
        llm_provider=llm["provider"],
        llm_model=llm["model"],
        llm_api_key=llm["api_key"],
        llm_base_url=llm["base_url"],
        embedding_provider=embedding_provider,
        embedding_model=rag["embedding_model"],
        embedding_api_key=rag["embedding_api_key"],
        embedding_base_url=provider_base_url(embedding_provider),
        chunk_size=rag["chunk_size"],
        chunk_overlap=rag["chunk_overlap"],
        top_k=rag["top_k"],
        fetch_k=rag["fetch_k"],
        lambda_mult=rag["mmr_lambda"],
        search_type=rag["search_type"],
        score_threshold=rag["score_threshold"],
    )


async def build_archives(ctx: RuntimeContext) -> ArchivesIngestion:
    """Build a scoped archive client without blocking the event loop."""
    settings = _archive_settings(ctx)
    scope = _archive_scope(ctx)
    if settings.vector_backend == "faiss" and scope != "default":
        data_dir = Path(settings.data_dir) / "projects" / scope
        index_path = data_dir / "faiss_index"
    else:
        data_dir = Path(settings.data_dir)
        index_path = Path(settings.index_path)

    return await asyncio.to_thread(
        ArchivesIngestion,
        data_dir=str(data_dir),
        index_path=str(index_path),
        settings=settings,
    )


async def get_archives_for_context(ctx: RuntimeContext) -> ArchivesIngestion:
    """Reuse archive clients per effective config and storage partition."""
    scope = _archive_scope(ctx) if _settings.vector_backend == "faiss" else "qdrant"
    key = f"archives:{ctx.config_signature}:{scope}"
    return await object_registry.get(key, lambda: build_archives(ctx))


async def _build_brain_bundle(ctx: RuntimeContext) -> NPCBrain:
    # NPCBrain construction is sync/CPU (embeddings + settings); offload.
    # Hand it the context's already-resolved settings. Passing only the LLM key made
    # NPCBrain re-resolve embeddings from that key too, so a chat-only key (Groq,
    # Cerebras, OpenRouter) silently moved the brain to a different embedding
    # provider than ingest, /health and the warmup use — a different vector space
    # than the index it then queries.
    return await asyncio.to_thread(
        NPCBrain, ctx.llm_settings["api_key"], settings=_archive_settings(ctx)
    )


async def get_brain(ctx: RuntimeContext) -> NPCBrain:
    return await object_registry.get(
        "brain:" + ctx.config_signature, lambda: _build_brain_bundle(ctx)
    )


@lru_cache(maxsize=1)
def get_default_archives() -> ArchivesIngestion:
    return ArchivesIngestion()


def get_archives(api_key: Optional[str] = None) -> ArchivesIngestion:
    if api_key:
        return ArchivesIngestion(api_key=api_key)
    return get_default_archives()


async def current_user(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> tuple[str, str]:
    """Resolve web identity: Bearer JWT or X-API-Key → (user_id, user_key).

    Falls back to the default user when auth is unconfigured / no credential.
    """
    if authorization and not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="authorization must use Bearer authentication",
        )
    jwt_token = authorization[7:].strip() if authorization else None
    if auth_enabled(_settings) and not (jwt_token or x_api_key):
        raise HTTPException(status_code=401, detail="authentication required")
    try:
        return await resolve_user(
            state_store,
            _settings,
            jwt_token=jwt_token,
            header_key=x_api_key,
            cache=identity_cache,
        )
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


# --- Ingestion / reindex workers ---------------------------------------------
# The queues are process-local infrastructure: `lifespan` starts and stops them,
# so they sit here with the other singletons. The handlers below are thin
# bindings -- they resolve the archive client (an api-layer concern, because it
# goes through object_registry) and hand the work to sentient.services.ingestion.


async def _ingest_handler(job: IngestJob) -> None:
    archives = job.archives or get_archives(job.api_key)
    await ingestion.run_ingest_job(job, state_store=state_store, archives=archives)


ingest_queue = IngestQueue(_ingest_handler)


async def enqueue_ingest(job: IngestJob) -> None:
    """Stable enqueue seam for replacing the process-local worker later."""
    await ingest_queue.enqueue(job)


async def _reindex_handler(job: ReindexJob) -> None:
    if job.user_id is None:
        archives = get_archives(job.api_key)
    else:
        ctx = await resolve_runtime_context(
            state_store,
            _settings,
            user_id=job.user_id,
            user_key=job.user_key or "default",
            project_id=job.project_id,
            provider_key=job.api_key,
        )
        archives = await get_archives_for_context(ctx)

    await ingestion.run_reindex_job(job, state_store=state_store, archives=archives)


reindex_queue = IngestQueue(_reindex_handler)


async def enqueue_reindex(job: ReindexJob) -> None:
    """Stable enqueue seam for project reindex jobs."""
    await reindex_queue.enqueue(job)


# Request-scoped tenant resolution for the key-in-path (Mantella) and
# upload/sources routes. It lives here rather than in a service for the same
# reason current_user does: it resolves *identity for this request* out of the
# process singletons, and it is wired straight into route signatures. It keeps
# raising HTTPException directly -- deps.py is the api layer, so HTTP vocabulary
# is legal here, and routing it through core.errors would only add a hop.

async def completions_ctx(
    api_key: str | None,
    project_id: str | None,
) -> RuntimeContext:
    provider_key = _as_provider_key(api_key)
    identity_key = None if provider_key and project_id is None else api_key
    try:
        user_id, user_key = await resolve_user(
            state_store,
            _settings,
            api_key=identity_key,
            cache=identity_cache,
        )
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    if project_id is not None:
        project = await state_store.get_project(user_id, project_id)
        if project is None:
            raise HTTPException(status_code=403, detail="project not found for this key")

    return await runtime_cache.resolve(
        state_store,
        _settings,
        user_id=user_id,
        user_key=user_key,
        project_id=project_id,
        session_id=None,
        provider_key=provider_key,
    )
