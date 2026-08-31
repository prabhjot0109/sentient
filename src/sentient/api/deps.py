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
import shutil
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

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
from sentient.core.logging import bind
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


def partition_name(user_key: str, project_id: str | None) -> str:
    """Return the opaque FAISS partition name for one tenant's project.

    Takes the two identity values rather than a RuntimeContext, because
    reclamation runs *after* the project row is deleted and there is no longer a
    context to resolve. Everything else calls it through `_archive_scope`.
    """
    if user_key == "default" and project_id is None:
        return "default"

    user = hashlib.sha256(user_key.encode("utf-8")).hexdigest()[:24]
    project = hashlib.sha256((project_id or "legacy").encode("utf-8")).hexdigest()[:24]
    return f"{user}-{project}"


def _archive_scope(ctx: RuntimeContext) -> str:
    """Return an opaque FAISS partition name for this runtime context.

    Qdrant applies the same identity at query time through payload filters. FAISS
    has no payload filtering, so it must use a physically separate index per
    user/project (while preserving the legacy env-default index for default
    requests).
    """
    return partition_name(ctx.user_key, ctx.project_id)


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


def get_archives(api_key: str | None = None) -> ArchivesIngestion:
    if api_key:
        return ArchivesIngestion(api_key=api_key)
    return get_default_archives()


def _bearer_token(authorization: str | None) -> str | None:
    """Extract a Bearer token, rejecting any other scheme."""
    if not authorization:
        return None
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="authorization must use Bearer authentication",
        )
    return authorization[7:].strip() or None


async def resolve_caller(
    *,
    jwt_token: str | None = None,
    api_key: str | None = None,
    provider_key: str | None = None,
) -> tuple[str, str]:
    """The one credential funnel: any credential in, `(user_id, user_key)` out.

    Every authenticated route resolves through here so the auth-enabled 401 is
    applied in exactly one place. `completions_ctx` used to run its own parallel
    resolution with no such check, which is how /v1/upload and /v1/sources served
    unauthenticated callers against the default tenant (spec A3).

    `provider_key` is never an identity -- it selects no user. It is accepted only
    so the legacy `/v1/<provider-key>/chat/completions` wiring still counts as
    "the caller sent a credential" and keeps resolving to the default tenant
    instead of 401-ing.
    """
    if auth_enabled(_settings) and not (jwt_token or api_key or provider_key):
        raise HTTPException(status_code=401, detail="authentication required")
    try:
        user_id, user_key = await resolve_user(
            state_store,
            _settings,
            jwt_token=jwt_token,
            api_key=api_key,
            cache=identity_cache,
        )
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    # The one funnel every authenticated route passes through, so binding here
    # puts the tenant on every log line the rest of the request emits. user_key
    # is an opaque hash of the user id, never a credential.
    bind(user_key=user_key, project_id=None, thread_id=None)
    return user_id, user_key


async def current_user(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> tuple[str, str]:
    """Resolve web identity: Bearer JWT or X-API-Key → (user_id, user_key).

    Falls back to the default user when auth is unconfigured / no credential.
    """
    return await resolve_caller(
        jwt_token=_bearer_token(authorization),
        api_key=x_api_key,
    )


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

    try:
        await ingestion.run_reindex_job(job, state_store=state_store, archives=archives)
    finally:
        # B6. run_reindex_job's last act is a DB write flipping the project back to
        # 'active', and nothing is watching that column: the reindex guard reads
        # ctx.status, and ctx comes from RuntimeCache, a TTLCache(ttl=60). Without
        # this the 409 outlives its own rebuild by up to a minute -- measured
        # 2026-08-23 at ~2 s of work followed by ~60 s of 409. finally, not else,
        # because the failure branch puts the project back to reindexing_required
        # and the next reader should not have to re-derive that invalidating is
        # harmless there. services/projects.py does the same thing for the three
        # write paths; this is the fourth.
        runtime_cache.invalidate(job.project_id)


reindex_queue = IngestQueue(_reindex_handler)


async def enqueue_reindex(job: ReindexJob) -> None:
    """Stable enqueue seam for project reindex jobs."""
    await reindex_queue.enqueue(job)


async def reclaim_project_storage(user_key: str, project_id: str) -> None:
    """Release the storage a deleted project leaves behind. Two backends, two ways.

    Called AFTER the row is gone, which rules out `resolve_runtime_context`: there
    is no project left to resolve. Both mechanisms need only the two identity
    values, which is why `partition_name` takes them directly.

    FAISS keeps a physically separate index per tenant, so the orphan is the
    partition DIRECTORY and `shutil.rmtree` is the reclamation.
    `FaissBackend.clear_project` is a documented no-op and calling it would look
    correct while reclaiming nothing.

    Qdrant keeps every tenant in one shared collection and isolates by payload
    filter, so `clear_project` deletes by that filter and there is no directory.
    The shared collection is also why the process-default archives client can do
    this at all: the filter carries the tenant, so the client does not have to be
    the deleted project's own.

    The Qdrant orphan is the one that actually hurts. A deleted project's points
    stay inside the same collection every live project shares, and nothing will
    ever reindex them away, because reindexing is a per-project operation and the
    project is gone.
    """
    if _settings.vector_backend == "faiss":
        partition = Path(_settings.data_dir) / "projects" / partition_name(user_key, project_id)
        await asyncio.to_thread(shutil.rmtree, partition, ignore_errors=True)
        return

    archives = get_default_archives()
    await asyncio.to_thread(archives.clear_project, user_key, project_id)


# Request-scoped tenant resolution for the key-in-path (Mantella) and
# upload/sources routes. It lives here rather than in a service for the same
# reason current_user does: it resolves *identity for this request* out of the
# process singletons, and it is wired straight into route signatures. It keeps
# raising HTTPException directly -- deps.py is the api layer, so HTTP vocabulary
# is legal here, and routing it through core.errors would only add a hop.


async def completions_ctx(
    api_key: str | None,
    project_id: str | None,
    *,
    jwt_token: str | None = None,
) -> RuntimeContext:
    provider_key = _as_provider_key(api_key)
    identity_key = None if provider_key and project_id is None else api_key
    user_id, user_key = await resolve_caller(
        jwt_token=jwt_token,
        api_key=identity_key,
        provider_key=provider_key,
    )

    if project_id is not None:
        project = await state_store.get_project(user_id, project_id)
        if project is None:
            raise HTTPException(status_code=403, detail="project not found for this key")
        bind(project_id=project_id)

    return await runtime_cache.resolve(
        state_store,
        _settings,
        user_id=user_id,
        user_key=user_key,
        project_id=project_id,
        session_id=None,
        provider_key=provider_key,
    )
