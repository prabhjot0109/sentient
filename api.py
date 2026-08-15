from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import tempfile
import time
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Any, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from sentient.adapters.stt import client as stt
from sentient.adapters.stt.diagnostics import analyse_wav, explain_empty_transcription
from sentient.adapters.auth import (
    AuthError,
    IdentityCache,
    auth_enabled,
    generate_api_key,
    resolve_user,
)
from logic.condense import condense_query
from sentient.core.config import (
    Provider,
    SearchType,
    load_rag_settings,
    provider_base_url,
)
from sentient.adapters.documents import ArchivesIngestion
from sentient.adapters.llm.openai_wire import (
    ChatCompletionRequest,
    OpenAIMessage,
    build_completion_response,
    format_lore,
    inject_lore,
    inject_persona,
    last_user_text,
    astream_completion,
    to_history,
    to_langchain,
)
from sentient.core.presets import list_presets
from sentient.core.crypto import crypto_available, encrypt_key, key_hint
from sentient.adapters.llm.models import build_chat_model
from sentient.core.cache import ObjectRegistry
from logic.runtime import RuntimeCache, RuntimeContext, embedding_signature, resolve_runtime_context
from sentient.adapters.state import get_state_store
from sentient.core.concurrency import IngestJob, IngestQueue, ReindexJob, SessionLocks, defer
from npc_brain import NPCBrain

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


async def _warm_grounding_path() -> None:
    """Pay every one-off cost on the lore path before the first player line does.

    With local embeddings this is not a micro-optimisation: loading
    BAAI/bge-base-en-v1.5 takes ~9s, FAISS then has to be read off disk, and torch
    only builds its execution graph on the first real forward pass. All three would
    otherwise land on whichever utterance happens to arrive first, and that one is
    always the player's opening line of a conversation.

    It must be a real retrieval — building the client without embedding anything
    leaves the torch cost unpaid. build_embeddings is lru_cached, so warming this
    instance warms every archive that resolves to the same embedding config.
    """
    started = perf_counter()
    await get_default_archives().retrieve(
        "warmup", k=1, search_type="similarity", min_score=0.0
    )
    print(f"[WARMUP] Lore path ready in {perf_counter() - started:.1f}s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start process-local workers and drain accepted work during shutdown."""
    await ingest_queue.start()
    await reindex_queue.start()
    try:
        have_provider_key = any_provider_key_present()
        try:
            if have_provider_key:
                # Build the on-disk index from data/ at boot if missing, so the Mantella
                # completions path has lore to ground on. Async so startup embedding
                # never blocks the event loop. No global brain — clients resolve per turn.
                await get_default_archives().ensure_index()
            else:
                print("No default API key found. Clients will initialize per-request.")
        except Exception as e:
            print(f"Startup initialization failed: {e}")

        # Deliberately awaited, not deferred: uvicorn should not report the server
        # ready while a request would still race the model load. A failure here is
        # not fatal — the cost is simply paid on first use — so it must never stop
        # startup (an empty data/ directory is a normal fresh-clone state). Skipped
        # without a provider key: there is no embedding client to warm, and building
        # one would load a model no request will resolve to.
        if have_provider_key:
            try:
                await _warm_grounding_path()
            except Exception as e:
                print(f"[WARMUP] Lore path warmup skipped ({e}); first request will be slower.")

        yield
    finally:
        await reindex_queue.stop()
        await ingest_queue.stop()
        print("Shutting down...")


app = FastAPI(title="Sentient AI API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # Vite picks the next free port (5174, 5175, ...) whenever 5173 is already
    # taken by another running dev server, so pin the allow-list to a regex
    # instead of a fixed port list to avoid breaking on port bumps.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    # Deployed frontends, from CORS_ALLOW_ORIGINS. FastAPI honours the list and the
    # regex together, so a production origin does not cost the dev-port coverage.
    allow_origins=list(_settings.cors_allow_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RetrievedChunk(BaseModel):
    content: str
    score: Optional[float] = None
    source: str
    page_label: str = ""
    chunk_id: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatInput(BaseModel):
    message: str
    api_key: Optional[str] = None
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    project_id: Optional[str] = None
    thread_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    success: bool
    sources: list[RetrievedChunk] = Field(default_factory=list)
    top_k: Optional[int] = None
    retrieval_ms: Optional[float] = None
    thread_id: Optional[str] = None


class RetrievalInput(BaseModel):
    query: str
    api_key: Optional[str] = None
    top_k: Optional[int] = Field(default=None, ge=1, le=20)


class RetrievalResponse(BaseModel):
    success: bool
    query: str
    top_k: int
    retrieval_ms: float
    chunks: list[RetrievedChunk] = Field(default_factory=list)


class KeyInput(BaseModel):
    label: Optional[str] = Field(default=None, max_length=200)


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    base_preset: str = Field(default="custom", min_length=1, max_length=100)


class ConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm_provider: Optional[Provider] = None
    embedding_provider: Optional[Provider] = None
    model_name: Optional[str] = None
    embedding_model_name: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    mrl_vector_size: Optional[int] = Field(default=None, ge=1)
    reasoning_effort: Optional[str] = None
    reasoning_format: Optional[str] = None
    rag_search_type: Optional[SearchType] = None
    rag_top_k: Optional[int] = Field(default=None, ge=1)
    rag_fetch_k: Optional[int] = Field(default=None, ge=1)
    rag_mmr_lambda: Optional[float] = Field(default=None, ge=0, le=1)
    rag_score_threshold: Optional[float] = Field(default=None, ge=0, le=1)
    rag_chunk_size: Optional[int] = Field(default=None, ge=1)
    rag_chunk_overlap: Optional[int] = Field(default=None, ge=0)
    persona_prompt: Optional[str] = None
    history_window: Optional[int] = Field(default=None, ge=1)


class PersonaInput(BaseModel):
    system_prompt: str


class CredentialInput(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    api_key: str = Field(min_length=1)


@lru_cache(maxsize=1)
def get_default_archives() -> ArchivesIngestion:
    return ArchivesIngestion()


def get_archives(api_key: Optional[str] = None) -> ArchivesIngestion:
    if api_key:
        return ArchivesIngestion(api_key=api_key)
    return get_default_archives()


async def _ingest_handler(job: IngestJob) -> None:
    archives = job.archives or get_archives(job.api_key)
    staged_path = Path(job.file_path)
    final_path = archives.data_dir / job.filename
    try:
        if staged_path != final_path:
            await asyncio.to_thread(final_path.parent.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(os.replace, staged_path, final_path)

        metadata = await archives.add_file(
            str(final_path),
            user_key=job.user_key,
            project_id=job.project_id,
            embedding_signature=job.embedding_signature,
        )
        if job.project_id is not None:
            await state_store.register_document(
                job.project_id,
                job.filename,
                (metadata or {}).get("added_chunk_count", 0),
                job.embedding_signature,
                status="ready",
            )
    except Exception:
        if job.project_id is not None:
            await state_store.set_document_status(
                job.project_id, job.filename, "failed"
            )
        raise
    finally:
        if staged_path != final_path and staged_path.exists():
            await asyncio.to_thread(staged_path.unlink)


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

    documents = await state_store.list_documents(job.project_id)
    try:
        await asyncio.to_thread(archives.clear_project, job.user_key, job.project_id)
        if archives.settings.vector_backend == "faiss":
            await asyncio.to_thread(archives.reset_index)

        for document in documents:
            await state_store.set_document_status(
                job.project_id, document["filename"], "reindexing"
            )
            metadata = await archives.add_file(
                str(archives.data_dir / document["filename"]),
                user_key=job.user_key,
                project_id=job.project_id,
                embedding_signature=job.embedding_signature,
            )
            await state_store.register_document(
                job.project_id,
                document["filename"],
                (metadata or {}).get("added_chunk_count", 0),
                job.embedding_signature,
                status="ready",
            )
        await state_store.set_project_status(job.project_id, "active")
    except Exception:
        await state_store.set_project_status(job.project_id, "reindexing_required")
        raise


reindex_queue = IngestQueue(_reindex_handler)


async def enqueue_reindex(job: ReindexJob) -> None:
    """Stable enqueue seam for project reindex jobs."""
    await reindex_queue.enqueue(job)


@app.get("/health")
def health_check():
    archives = get_default_archives()
    settings = load_rag_settings()
    index_metadata = archives.get_index_metadata()

    return {
        "status": "online",
        "brain_loaded": object_registry.size() > 0,
        "index_loaded": archives.index_exists(),
        "source_count": len(archives.list_sources()),
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "search_type": settings.search_type,
        "top_k": settings.top_k,
        "persona": index_metadata.get("persona") if index_metadata else None,
        "index_metadata": index_metadata,
    }


@app.post("/v1/chat", response_model=ChatResponse)
async def chat_endpoint(
    payload: ChatInput,
    user: tuple[str, str] = Depends(current_user),
):
    try:
        started_at = perf_counter()
        provider_key = _as_provider_key(payload.api_key)
        if not (provider_key or any_provider_key_present() or _settings.sentient_secret_key):
            raise ValueError("API Key not found. Please provide one or set it in .env")

        user_id, user_key = user
        if payload.thread_id and not payload.project_id:
            raise HTTPException(status_code=400, detail="thread_id requires project_id")

        if payload.project_id:
            project = await state_store.get_project(user_id, payload.project_id)
            if project is None:
                raise HTTPException(status_code=404, detail="project not found")

            if payload.thread_id:
                thread = await state_store.get_thread(user_id, payload.thread_id)
                if thread is None or thread["project_id"] != payload.project_id:
                    raise HTTPException(status_code=404, detail="thread not found")
            else:
                thread = await state_store.upsert_thread(
                    payload.project_id,
                    uuid4().hex,
                    title=payload.message.strip()[:60] or "New chat",
                )

            ctx = await runtime_cache.resolve(
                state_store,
                _settings,
                user_id=user_id,
                user_key=user_key,
                project_id=payload.project_id,
                session_id=thread["id"],
                provider_key=provider_key,
            )
            history_window = (await state_store.get_project_config(payload.project_id) or {}).get(
                "history_window"
            ) or 20
            history = await state_store.list_messages(thread["id"], limit=history_window)
            result = await _run_web_project_chat(ctx, history, payload.message, payload.top_k)
            defer(
                _store_web_thread_turn(thread["id"], payload.message, result["answer"]),
                label="thread-memory",
            )
            elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
            return ChatResponse(
                response=result["answer"],
                success=True,
                sources=[RetrievedChunk(**source) for source in result["sources"]],
                top_k=result["top_k"],
                retrieval_ms=elapsed_ms,
                thread_id=thread["id"],
            )

        ctx = await runtime_cache.resolve(
            state_store,
            _settings,
            user_id=user_id,
            user_key=user_key,
            project_id=None,
            session_id=None,
            provider_key=provider_key,
        )
        active_brain = await get_brain(ctx)
        result = await active_brain.ask_with_context(payload.message, top_k=payload.top_k)
        elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
        return ChatResponse(
            response=result["answer"],
            success=True,
            sources=[RetrievedChunk(**source) for source in result["sources"]],
            top_k=result["top_k"],
            retrieval_ms=elapsed_ms,
        )
    except ValueError:
        return ChatResponse(
            response="Please provide an API key or set it in the environment.",
            success=False,
        )
    except HTTPException:
        raise  # ownership/validation statuses must survive the catch-all below
    except Exception as e:
        print(f"Chat Endpoint Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _run_web_project_chat(ctx, history, message, top_k):
    """Generate a project web turn with bounded durable history before the new turn."""
    if ctx.status == "reindexing_required":
        raise HTTPException(status_code=409, detail="project is reindexing; retrieval temporarily unavailable")

    async def _retrieve():
        try:
            archives = await get_archives_for_context(ctx)
            return await archives.retrieve(
                message,
                k=top_k or ctx.rag_settings["top_k"],
                search_type=ctx.rag_settings["search_type"],
                min_score=ctx.rag_settings["score_threshold"],
                user_key=ctx.user_key,
                project_id=ctx.project_id,
                embedding_signature=embedding_signature(ctx.rag_settings),
            )
        except Exception as exc:
            print(f"Lore retrieval failed (answering without grounding): {exc}")
            return []

    llm, chunks = await asyncio.gather(get_llm(ctx), _retrieve())
    turn_messages = [OpenAIMessage(role=row["role"], content=row["content"]) for row in history]
    turn_messages.append(OpenAIMessage(role="user", content=message))
    messages = inject_persona(to_langchain(turn_messages), ctx.system_prompt)
    messages = inject_lore(messages, format_lore(chunks))
    result = await llm.ainvoke(messages)
    sources = [
        {
            "content": document.page_content,
            "score": score,
            "source": document.metadata.get("source", "unknown"),
            "page_label": document.metadata.get("page_label", ""),
            "chunk_id": document.metadata.get("chunk_id"),
            "metadata": dict(document.metadata),
        }
        for document, score in chunks
    ]
    return {"answer": str(result.content), "sources": sources, "top_k": top_k or ctx.rag_settings["top_k"]}


async def _store_web_thread_turn(thread_id: str, message: str, reply: str) -> None:
    async with session_locks.lock(thread_id):
        await state_store.add_message(thread_id, "user", message)
        await state_store.add_message(thread_id, "assistant", reply)


@app.post("/v1/retrieve", response_model=RetrievalResponse)
async def retrieve_endpoint(payload: RetrievalInput):
    try:
        started_at = perf_counter()
        archives = get_archives(payload.api_key)
        chunks = await archives.retrieve(payload.query, k=payload.top_k)
        elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
        serialized_chunks = [
            RetrievedChunk(
                content=document.page_content,
                score=score,
                source=document.metadata.get("source", "unknown"),
                page_label=document.metadata.get("page_label", ""),
                chunk_id=document.metadata.get("chunk_id"),
                metadata=document.metadata,
            )
            for document, score in chunks
        ]
        return RetrievalResponse(
            success=True,
            query=payload.query,
            top_k=payload.top_k or load_rag_settings(payload.api_key).top_k,
            retrieval_ms=elapsed_ms,
            chunks=serialized_chunks,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _run_completions(
    request: ChatCompletionRequest,
    ctx: RuntimeContext,
    *,
    context_ms: float = 0.0,
):
    if ctx.project_id and ctx.status == "reindexing_required":
        raise HTTPException(
            status_code=409,
            detail="project is reindexing; retrieval temporarily unavailable",
        )
    model_name = ctx.llm_settings["model"]
    query = last_user_text(request.messages)
    print(
        f"[Mantella:{ctx.user_key}] >> {ctx.llm_settings['provider']}/{model_name} "
        f"(stream={request.stream}) | project={ctx.project_id} | query: {query.strip()!r}"
    )

    async def _retrieve(retrieval_query: str, archives=None) -> list:
        if not retrieval_query.strip():
            return []
        try:
            resolved_archives = archives or await get_archives_for_context(ctx)
            search_type = (
                ctx.rag_settings["search_type"] if ctx.project_id else "similarity"
            )
            return await resolved_archives.retrieve(
                retrieval_query,
                k=ctx.rag_settings["top_k"],
                search_type=search_type,
                min_score=ctx.rag_settings["score_threshold"],
                user_key=ctx.user_key,
                project_id=ctx.project_id,
                embedding_signature=embedding_signature(ctx.rag_settings),
            )
        except Exception as e:
            print(f"Lore retrieval failed (answering without grounding): {e}")
            return []

    ground_started = perf_counter()
    if _settings.condense_queries and query.strip():
        llm, archives = await asyncio.gather(
            get_llm(ctx), get_archives_for_context(ctx)
        )
        retrieval_query = await condense_query(
            llm, to_history(request.messages), query
        )
        if retrieval_query != query:
            print(
                f"[Mantella:{ctx.user_key}]   condensed: {query.strip()!r} "
                f"-> {retrieval_query.strip()!r}"
            )
        chunks = await _retrieve(retrieval_query, archives)
    else:
        llm, chunks = await asyncio.gather(get_llm(ctx), _retrieve(query))
    ground_ms = (perf_counter() - ground_started) * 1000

    print(f"[Mantella:{ctx.user_key}]   retrieved {len(chunks)} lore chunk(s)")
    prompt_started = perf_counter()
    messages = inject_persona(to_langchain(request.messages), ctx.system_prompt)
    messages = inject_lore(messages, format_lore(chunks))
    prompt_ms = (perf_counter() - prompt_started) * 1000
    print(
        f"[turn:{ctx.user_key}] ctx={context_ms:.1f}ms "
        f"ground={ground_ms:.1f}ms prompt={prompt_ms:.1f}ms"
    )

    if request.stream:
        print(f"[Mantella:{ctx.user_key}]   << streaming reply")
        return StreamingResponse(
            _stream_with_deferred_turn_work(llm, messages, model_name, ctx),
            media_type="text/event-stream",
        )

    result = await llm.ainvoke(messages)
    reply = str(result.content)
    print(f"[Mantella:{ctx.user_key}]   << reply ({len(reply)} chars): {reply!r}")
    _schedule_deferred_turn_work(ctx)
    return build_completion_response(reply, model_name)


async def _stream_with_deferred_turn_work(
    llm: Any,
    messages: list,
    model_name: str,
    ctx: RuntimeContext,
):
    """Keep the response path lock-free; queue post-turn work after streaming ends."""
    try:
        async for event in astream_completion(llm, messages, model_name):
            yield event
    finally:
        _schedule_deferred_turn_work(ctx)


async def _deferred_turn_work(ctx: RuntimeContext) -> None:
    """Surface game sessions in the sidebar. Write-only: the game path never reads
    server-side memory — Mantella carries the conversation in its own payload."""
    assert ctx.session_id is not None
    async with session_locks.lock(ctx.session_id):
        await state_store.upsert_thread(ctx.project_id, ctx.session_id, npc_name=ctx.npc_name)


def _schedule_deferred_turn_work(ctx: RuntimeContext) -> None:
    if ctx.session_id and ctx.project_id:
        defer(_deferred_turn_work(ctx), label="session-turn")


async def _completions_ctx(
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


@app.post("/v1/chat/completions")
async def openai_chat_completions(
    request: ChatCompletionRequest,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """OpenAI-compatible env-default route retained for existing clients."""
    try:
        context_started = perf_counter()
        ctx = await _completions_ctx(x_api_key, None)
        context_ms = (perf_counter() - context_started) * 1000
        return await _run_completions(request, ctx, context_ms=context_ms)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Chat Completions Error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/v1/{api_key}/chat/completions")
async def openai_chat_completions_key(
    api_key: str,
    request: ChatCompletionRequest,
):
    context_started = perf_counter()
    ctx = await _completions_ctx(api_key, None)
    context_ms = (perf_counter() - context_started) * 1000
    return await _run_completions(request, ctx, context_ms=context_ms)


@app.post("/v1/{api_key}/{project_id}/chat/completions")
async def openai_chat_completions_project(
    api_key: str,
    project_id: str,
    request: ChatCompletionRequest,
):
    context_started = perf_counter()
    ctx = await _completions_ctx(api_key, project_id)
    if request.session_id:
        ctx = replace(ctx, session_id=request.session_id, npc_name=request.npc_name)
    context_ms = (perf_counter() - context_started) * 1000
    return await _run_completions(request, ctx, context_ms=context_ms)


@app.get("/v1/models")
def list_models():
    """Minimal model list so OpenAI-compatible clients can populate their UI.

    Clients like Mantella read this through the OpenAI Python SDK, whose `Model`
    type requires `id`, `object`, `created`, and `owned_by`. Omitting `created`
    makes the SDK's Pydantic parse raise even though the HTTP call succeeds, so
    we always include it.
    """
    settings = load_rag_settings()
    return {
        "object": "list",
        "data": [
            {
                "id": settings.llm_model,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "sentient",
            }
        ],
    }


# Recent transcriptions, newest last. Exposed so mic problems can be reviewed after
# the fact instead of scrollbacking the console during a play session.
_STT_HISTORY: list[dict] = []
_STT_HISTORY_LIMIT = 50


def _record_stt_history(entry: dict) -> None:
    _STT_HISTORY.append(entry)
    del _STT_HISTORY[:-_STT_HISTORY_LIMIT]


@app.post("/v1/audio/transcriptions")
async def audio_transcriptions(
    file: UploadFile = File(...),
    model: str = Form(stt.GROQ_DEFAULT_MODEL),
    language: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
    response_format: Optional[str] = Form("json"),
    temperature: Optional[float] = Form(0.0),
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """OpenAI-compatible speech-to-text that doubles as a microphone diagnostic.

    NOTE: this is the ONE route where `Authorization: Bearer` is a *provider* key
    rather than a Neon Auth JWT — Mantella's UI has a single field for its Whisper
    credential and forwards it here. It therefore does not use `Depends(current_user)`;
    Sentient identity comes from `X-API-Key` only. Do not "fix" this to match the
    other routes without changing what Mantella sends.

    Point Mantella's Speech-to-Text -> Whisper URL at this endpoint and every
    utterance is measured (duration, RMS, peak, clipping) and printed alongside the
    text, which is the only way to tell a dead microphone apart from an STT model
    that simply heard nothing.
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    contents = await file.read()
    filename = file.filename or "audio.wav"
    # numpy work on a multi-second capture: cheap (~1ms) but still CPU, and this
    # route is on the critical path of every spoken line.
    report = await asyncio.to_thread(analyse_wav, contents)

    user_id = None
    if x_api_key:
        try:
            user_id, _ = await resolve_user(
                state_store, _settings, api_key=x_api_key, cache=identity_cache
            )
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e)) from e

    provider, api_key, key_source = await stt.resolve_stt_credential(
        state_store, _settings, authorization=authorization, user_id=user_id
    )

    print("\n" + "=" * 65)
    print(f"[STT] Mic input received at {timestamp}")
    print(f"   File     : {filename} ({len(contents) / 1024:.1f} KB)")
    if report.sample_rate:
        print(
            f"   Audio    : {report.duration_s:.2f}s  {report.sample_rate} Hz  "
            f"{report.channels}ch  {report.sample_width * 8}-bit"
        )
        print(
            f"   Level    : [{report.level_bar()}] RMS {report.rms * 100:5.2f}%  "
            f"peak {report.peak * 100:5.1f}%"
        )
    print(f"   Verdict  : {report.verdict} - {report.detail}")
    for warning in report.warnings:
        print(f"   ! {warning}")

    if provider is None:
        message = (
            "No speech-to-text credential available: set GROQ_API_KEY or OPENAI_API_KEY "
            "in .env, upload one via POST /v1/credentials, or let Mantella forward its "
            "own key via the Authorization header."
        )
        print(f"   [ERROR] {message}")
        print("=" * 65 + "\n")
        raise HTTPException(status_code=400, detail=message)

    stt_model = stt.upstream_model(provider, model)
    # The key itself is never logged, only where it came from.
    print(f"   Upstream : {provider} / {stt_model}  (key from {key_source})")

    # The SDKs serialise an explicit None, so optional fields are only sent when set.
    options: dict[str, Any] = {
        "file": (filename, contents),
        "model": stt_model,
        "response_format": "json",
        "temperature": temperature or 0.0,
    }
    if language and language not in ("default", "auto"):
        options["language"] = language
    if prompt:
        options["prompt"] = prompt

    started = perf_counter()
    try:
        # The SDK call is blocking; running it inline would stall the event loop for
        # the whole upload + transcription, starving every other tenant's turn.
        client = stt.stt_client(provider, api_key)
        response = await asyncio.to_thread(client.audio.transcriptions.create, **options)
    except Exception as e:
        print(f"   [ERROR] {provider} transcription failed: {e}")
        print("=" * 65 + "\n")
        _record_stt_history(
            {
                "time": timestamp,
                "text": "",
                "error": str(e),
                "provider": provider,
                "model": stt_model,
                "audio": report.as_dict(),
            }
        )
        raise HTTPException(status_code=502, detail=f"{provider} STT failed: {e}") from e

    elapsed = perf_counter() - started
    text = str(getattr(response, "text", response) or "").strip()

    discarded = ""
    if text and report.carries_no_speech:
        discarded = text
        # The waveform holds no speech, so this text was invented by the model.
        # Dropping it makes Mantella report "could not detect speech" and replay the
        # cue, instead of the NPC answering a line the player never spoke.
        print(f'   DISCARDED: "{text}" - hallucinated from {report.verdict.lower()} audio')
        print(f"   [WHY] {report.detail}")
        text = ""

    if text:
        print(f'   HEARD    : "{text}"   ({elapsed:.2f}s)')
    else:
        print(f"   HEARD    : <nothing>   ({elapsed:.2f}s)")
        if not discarded:
            print(f"   [WHY] {explain_empty_transcription(report)}")
    print("=" * 65 + "\n")

    _record_stt_history(
        {
            "time": timestamp,
            "text": text,
            "discarded_hallucination": discarded,
            "error": None,
            "provider": provider,
            "model": stt_model,
            "elapsed_s": round(elapsed, 3),
            "audio": report.as_dict(),
        }
    )

    if response_format == "text":
        return PlainTextResponse(text)
    if response_format == "verbose_json":
        return {
            "task": "transcribe",
            "language": language or "auto",
            "duration": round(report.duration_s, 3),
            "text": text,
            "segments": [],
        }
    return {"text": text}


@app.get("/v1/audio/transcriptions/recent")
def recent_transcriptions(limit: int = 20):
    """The last few utterances with their measured mic levels, for debugging."""
    window = _STT_HISTORY[-max(1, min(limit, _STT_HISTORY_LIMIT)):]
    return {
        "count": len(window),
        "empty_transcriptions": sum(1 for item in window if not item["text"]),
        "transcriptions": list(reversed(window)),
    }


@app.post("/v1/keys")
async def create_key(
    payload: KeyInput,
    user: tuple[str, str] = Depends(current_user),
):
    user_id, _ = user
    raw_key, key_hash = generate_api_key()
    row = await state_store.create_api_key(user_id, key_hash, label=payload.label)
    return {"id": row["id"], "api_key": raw_key, "label": payload.label}


_CREDENTIAL_PROVIDERS = {"google", "openai", "huggingface", "groq", "cerebras", "openrouter"}


def _credential_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized not in _CREDENTIAL_PROVIDERS:
        raise HTTPException(status_code=400, detail="unknown provider")
    return normalized


def _credential_secret() -> str:
    if not crypto_available(_settings):
        raise HTTPException(status_code=503, detail="credential vault is not configured")
    return _settings.sentient_secret_key


async def _invalidate_user_projects(user_id: str) -> None:
    for project in await state_store.list_projects(user_id):
        runtime_cache.invalidate(project["id"])


@app.post("/v1/credentials")
async def create_credential(
    payload: CredentialInput,
    user: tuple[str, str] = Depends(current_user),
):
    secret = _credential_secret()  # gate on the vault before validating anything else
    provider = _credential_provider(payload.provider)
    try:
        encrypted = encrypt_key(payload.api_key, secret)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="credential vault is unavailable") from exc
    user_id, _ = user
    row = await state_store.upsert_credential(user_id, provider, encrypted, key_hint(payload.api_key))
    await _invalidate_user_projects(user_id)
    return {"provider": row["provider"], "key_hint": row["key_hint"]}


@app.get("/v1/credentials")
async def list_credentials(user: tuple[str, str] = Depends(current_user)):
    _credential_secret()
    user_id, _ = user
    return {"credentials": await state_store.list_credentials(user_id)}


@app.delete("/v1/credentials/{provider}")
async def delete_credential(
    provider: str,
    user: tuple[str, str] = Depends(current_user),
):
    _credential_secret()
    user_id, _ = user
    deleted = await state_store.delete_credential(user_id, _credential_provider(provider))
    await _invalidate_user_projects(user_id)
    return {"deleted": deleted}


@app.get("/v1/keys")
async def list_keys(user: tuple[str, str] = Depends(current_user)):
    user_id, _ = user
    return {"keys": await state_store.list_api_keys(user_id)}


@app.delete("/v1/keys/{key_id}")
async def delete_key(
    key_id: str,
    user: tuple[str, str] = Depends(current_user),
):
    user_id, _ = user
    revoked = await state_store.revoke_api_key(user_id, key_id)
    if revoked:
        identity_cache.clear()
    return {"revoked": revoked}


@app.post("/v1/projects")
async def create_project(
    payload: ProjectInput,
    user: tuple[str, str] = Depends(current_user),
):
    user_id, _ = user
    project = await state_store.create_project(
        user_id,
        payload.name,
        payload.base_preset,
    )
    ctx = await resolve_runtime_context(
        state_store,
        _settings,
        user_id=user_id,
        user_key="_",
        project_id=project["id"],
    )
    await state_store.upsert_project_config(
        project["id"], embedding_signature=embedding_signature(ctx.rag_settings)
    )
    return project


@app.get("/v1/projects")
async def list_projects(user: tuple[str, str] = Depends(current_user)):
    user_id, _ = user
    return {"projects": await state_store.list_projects(user_id)}


@app.get("/v1/projects/{project_id}/threads")
async def list_project_threads(
    project_id: str,
    user: tuple[str, str] = Depends(current_user),
):
    user_id, _ = user
    if await state_store.get_project(user_id, project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    return {"threads": await state_store.list_threads(project_id)}


class ProjectRenameInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)


@app.patch("/v1/projects/{project_id}")
async def rename_project_endpoint(
    project_id: str,
    payload: ProjectRenameInput,
    user: tuple[str, str] = Depends(current_user),
):
    user_id, _ = user
    project = await state_store.rename_project(user_id, project_id, payload.name)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@app.delete("/v1/projects/{project_id}")
async def delete_project_endpoint(
    project_id: str,
    user: tuple[str, str] = Depends(current_user),
):
    """Delete a project and everything under it (config, threads, messages, documents).

    Vectors are NOT removed here — orphaned partitions are unreachable because every
    query filters on user_key+project_id, so this is disk cost, not a leak. Reclaiming
    it is tracked in the post-R8 TODO under "Storage reclamation".
    """
    user_id, _ = user
    if not await state_store.delete_project(user_id, project_id):
        raise HTTPException(status_code=404, detail="project not found")
    # Without this, cached contexts keep serving turns for a deleted project until
    # the RuntimeCache TTL expires.
    runtime_cache.invalidate(project_id)
    return {"deleted": True}


@app.delete("/v1/threads/{thread_id}")
async def delete_thread_endpoint(
    thread_id: str,
    user: tuple[str, str] = Depends(current_user),
):
    user_id, _ = user
    if not await state_store.delete_thread(user_id, thread_id):
        raise HTTPException(status_code=404, detail="thread not found")
    return {"deleted": True}


@app.get("/v1/projects/{project_id}/documents")
async def list_project_documents(
    project_id: str,
    user: tuple[str, str] = Depends(current_user),
):
    """Ingestion status per document — the completion signal for /v1/upload's 202."""
    user_id, _ = user
    if await state_store.get_project(user_id, project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    return {"documents": await state_store.list_documents(project_id)}


@app.get("/v1/threads/{thread_id}/messages")
async def list_thread_messages(
    thread_id: str,
    limit: int = 50,
    user: tuple[str, str] = Depends(current_user),
):
    if not 1 <= limit <= 200:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 200")
    user_id, _ = user
    if await state_store.get_thread(user_id, thread_id) is None:
        raise HTTPException(status_code=404, detail="thread not found")
    return {"messages": await state_store.list_messages(thread_id, limit=limit)}


@app.put("/v1/projects/{project_id}/config")
async def update_config(
    project_id: str,
    payload: ConfigInput,
    user: tuple[str, str] = Depends(current_user),
):
    user_id, _ = user
    project = await state_store.get_project(user_id, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    prior = (await state_store.get_project_config(project_id) or {}).get(
        "embedding_signature"
    )
    await state_store.upsert_project_config(
        project_id,
        **payload.model_dump(exclude_unset=True),
    )
    ctx = await resolve_runtime_context(
        state_store,
        _settings,
        user_id=user_id,
        user_key="_",
        project_id=project_id,
    )
    config = await state_store.upsert_project_config(
        project_id, embedding_signature=embedding_signature(ctx.rag_settings)
    )
    new_signature = config["embedding_signature"]
    runtime_cache.invalidate(project_id)
    if (
        prior is not None
        and prior != new_signature
        and project["status"] != "reindexing_required"
    ):
        await state_store.set_project_status(project_id, "reindexing_required")
        await enqueue_reindex(
            ReindexJob(
                project_id=project_id,
                user_key=user[1],
                api_key=None,
                embedding_signature=new_signature,
                user_id=user_id,
            )
        )
    return config


@app.put("/v1/projects/{project_id}/persona")
async def set_persona(
    project_id: str,
    payload: PersonaInput,
    user: tuple[str, str] = Depends(current_user),
):
    user_id, _ = user
    if await state_store.get_project(user_id, project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    config = await state_store.upsert_project_config(
        project_id,
        persona_prompt=payload.system_prompt,
    )
    runtime_cache.invalidate(project_id)
    return config


@app.get("/v1/presets")
async def presets_endpoint():
    return {"presets": list_presets()}


@app.post("/v1/upload", status_code=202)
async def upload_file(
    file: UploadFile = File(...),
    api_key: Optional[str] = Form(default=None),
    project_id: Optional[str] = Form(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """Stage an upload and enqueue non-blocking, tenant-scoped ingestion."""
    staged_path: str | None = None
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        safe_name = os.path.basename(file.filename)
        if not safe_name.lower().endswith((".pdf", ".txt")):
            raise HTTPException(
                status_code=400,
                detail="Only PDF and TXT files are supported",
            )

        credential = x_api_key or api_key
        ctx = await _completions_ctx(credential, project_id)
        archives = await get_archives_for_context(ctx)
        staging_dir = archives.data_dir / ".ingest"

        def _stage_upload() -> str:
            staging_dir.mkdir(parents=True, exist_ok=True)
            fd, path = tempfile.mkstemp(
                prefix="upload-", suffix=Path(safe_name).suffix, dir=staging_dir
            )
            with os.fdopen(fd, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            return path

        staged_path = await asyncio.to_thread(_stage_upload)
        signature = ""
        if project_id is not None:
            signature = embedding_signature(ctx.rag_settings)
            await state_store.register_document(
                project_id,
                safe_name,
                0,
                signature,
                status="processing",
            )

        job = IngestJob(
            project_id=project_id,
            user_key=ctx.user_key,
            api_key=ctx.llm_settings["api_key"],
            file_path=staged_path,
            filename=safe_name,
            embedding_signature=signature,
            archives=archives,
        )
        try:
            await enqueue_ingest(job)
        except (asyncio.QueueFull, RuntimeError) as exc:
            if project_id is not None:
                await state_store.set_document_status(project_id, safe_name, "failed")
            raise HTTPException(
                status_code=503, detail="ingestion queue is unavailable"
            ) from exc

        return {"status": "processing", "filename": safe_name}
    except HTTPException:
        if staged_path and os.path.exists(staged_path):
            await asyncio.to_thread(os.remove, staged_path)
        raise
    except Exception as e:
        if staged_path and os.path.exists(staged_path):
            await asyncio.to_thread(os.remove, staged_path)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/v1/sources")
async def list_sources(
    project_id: Optional[str] = None,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """List source documents for the caller's archive partition.

    Uploads land in `get_archives_for_context(ctx)` — a per-user/per-project FAISS
    partition — so listing must resolve the same context, or it reports a different
    archive than the one just written to. No key and no project_id resolves to the
    default partition, identical to the pre-R8 behaviour.
    """
    ctx = await _completions_ctx(x_api_key, project_id)
    archives = await get_archives_for_context(ctx)
    # stat()s every file in the partition: filesystem I/O, off the event loop.
    sources = await asyncio.to_thread(archives.list_sources)
    return {"sources": sources, "count": len(sources)}


@app.delete("/v1/sources/{filename}")
async def delete_source(
    filename: str,
    project_id: Optional[str] = None,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """Delete a source document from the caller's partition and its registry row.

    Resolving through _completions_ctx (rather than the api-key-only helper it used
    before) is what makes a project's documents deletable at all; clearing the
    documents row is what stops /v1/projects/{id}/documents reporting a file that is
    no longer on disk.
    """
    ctx = await _completions_ctx(x_api_key, project_id)
    archives = await get_archives_for_context(ctx)
    safe_name = os.path.basename(filename)
    file_path = archives.data_dir / safe_name

    if not await asyncio.to_thread(file_path.exists):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        await asyncio.to_thread(os.remove, file_path)
        index_metadata = await archives.remove_file(safe_name)
        if project_id is not None:
            await state_store.delete_document(project_id, safe_name)

        return {
            "success": True,
            "message": f"File '{safe_name}' deleted.",
            "index_metadata": index_metadata,
        }
    except HTTPException:
        # R7's delta records that chat_endpoint's blanket `except Exception -> 500`
        # swallowed its ownership HTTPExceptions and turned every 404 into a 500.
        # This handler has the same shape; do not repeat that bug.
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
