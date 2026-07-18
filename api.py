from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import tempfile
import time
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Any, List, Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from logic.auth import (
    AuthError,
    IdentityCache,
    auth_enabled,
    generate_api_key,
    resolve_user,
)
from logic.condense import condense_query
from logic.config import (
    Provider,
    SearchType,
    load_rag_settings,
    provider_api_key,
    provider_base_url,
)
from logic.ingestion import ArchivesIngestion
from logic.openai_adapter import (
    ChatCompletionRequest,
    build_completion_response,
    format_lore,
    inject_lore,
    inject_persona,
    last_user_text,
    astream_completion,
    to_history,
    to_langchain,
)
from logic.presets import list_presets
from logic.rag_engine import build_chat_model
from logic.registry import ObjectRegistry
from logic.runtime import RuntimeCache, RuntimeContext, embedding_signature, resolve_runtime_context
from logic.sqlite_chat_store import SQLiteChatStore
from logic.state import get_state_store
from logic.workers import IngestJob, IngestQueue, SessionLocks, defer
from npc_brain import NPCBrain

try:
    from supabase import Client, create_client
except ImportError:
    Client = Any  # type: ignore[misc,assignment]
    create_client = None

# Runtime caches (not a global brain). Clients are built once per config_signature
# and reused; config/persona writes invalidate RuntimeCache for that project.
_settings = load_rag_settings()
state_store = get_state_store(_settings)
identity_cache = IdentityCache()
runtime_cache = RuntimeCache()
object_registry = ObjectRegistry()
supabase_client: Optional[Client] = None
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
        embedding_api_key=provider_api_key(embedding_provider, llm["api_key"]),
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
    return await asyncio.to_thread(NPCBrain, ctx.llm_settings["api_key"])


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start process-local workers and drain accepted work during shutdown."""
    await ingest_queue.start()
    try:
        try:
            if any_provider_key_present():
                # Build the on-disk index from data/ at boot if missing, so the Mantella
                # completions path has lore to ground on. Async so startup embedding
                # never blocks the event loop. No global brain — clients resolve per turn.
                await get_default_archives().ensure_index()
            else:
                print("No default API key found. Clients will initialize per-request.")
        except Exception as e:
            print(f"Startup initialization failed: {e}")

        yield
    finally:
        await ingest_queue.stop()
        print("Shutting down...")


app = FastAPI(title="Sentient AI API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # Vite picks the next free port (5174, 5175, ...) whenever 5173 is already
    # taken by another running dev server, so pin the allow-list to a regex
    # instead of a fixed port list to avoid breaking on port bumps.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
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


class ChatResponse(BaseModel):
    response: str
    success: bool
    sources: list[RetrievedChunk] = Field(default_factory=list)
    top_k: Optional[int] = None
    retrieval_ms: Optional[float] = None


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


class StoredMessage(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str
    sources: Optional[List[dict]] = None


class ChatSessionPayload(BaseModel):
    client_id: str
    title: str
    preview: str = ""
    messages: List[StoredMessage] = Field(default_factory=list)


class ChatSessionSummary(BaseModel):
    id: str
    title: str
    preview: str
    created_at: str
    updated_at: str
    message_count: int


class ChatSessionDetail(ChatSessionSummary):
    messages: List[StoredMessage]


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


@lru_cache(maxsize=1)
def get_default_archives() -> ArchivesIngestion:
    return ArchivesIngestion()


@lru_cache(maxsize=1)
def get_local_chat_store() -> SQLiteChatStore:
    settings = load_rag_settings()
    return SQLiteChatStore(os.path.join(settings.data_dir, "chat_sessions.db"))


def current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def has_supabase_chat_store() -> bool:
    return bool(
        create_client is not None
        and os.getenv("SUPABASE_URL")
        and os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    )


def get_supabase_client() -> Client:
    global supabase_client

    if supabase_client is not None:
        return supabase_client

    if create_client is None:
        raise RuntimeError(
            "Supabase Python client is not installed. Run `uv sync` to install it."
        )

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key:
        raise RuntimeError("Supabase storage is not configured.")

    supabase_client = create_client(supabase_url, supabase_key)
    return supabase_client


def serialize_session_summary(record: dict) -> ChatSessionSummary:
    messages = record.get("messages") or []
    return ChatSessionSummary(
        id=record["id"],
        title=record.get("title") or "New chat",
        preview=record.get("preview") or "",
        created_at=record.get("created_at") or "",
        updated_at=record.get("updated_at") or record.get("created_at") or "",
        message_count=len(messages),
    )


def serialize_session_detail(record: dict) -> ChatSessionDetail:
    summary = serialize_session_summary(record)
    messages = record.get("messages") or []
    return ChatSessionDetail(**summary.model_dump(), messages=messages)


def list_chat_records(client_id: str) -> list[dict]:
    if has_supabase_chat_store():
        response = (
            get_supabase_client()
            .table("chat_sessions")
            .select("*")
            .eq("client_id", client_id)
            .order("updated_at", desc=True)
            .execute()
        )
        return response.data or []

    return get_local_chat_store().list(client_id)


def get_chat_record(chat_id: str, client_id: str) -> dict | None:
    if has_supabase_chat_store():
        response = (
            get_supabase_client()
            .table("chat_sessions")
            .select("*")
            .eq("id", chat_id)
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    return get_local_chat_store().get(chat_id, client_id)


def create_chat_record(payload: ChatSessionPayload) -> dict:
    message_payload = [message.model_dump() for message in payload.messages]

    if has_supabase_chat_store():
        timestamp = current_timestamp()
        response = (
            get_supabase_client()
            .table("chat_sessions")
            .insert(
                {
                    "client_id": payload.client_id,
                    "title": payload.title or "New chat",
                    "preview": payload.preview,
                    "messages": message_payload,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
            )
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create chat")
        return response.data[0]

    return get_local_chat_store().create(
        client_id=payload.client_id,
        title=payload.title,
        preview=payload.preview,
        messages=message_payload,
    )


def update_chat_record(chat_id: str, payload: ChatSessionPayload) -> dict | None:
    message_payload = [message.model_dump() for message in payload.messages]

    if has_supabase_chat_store():
        response = (
            get_supabase_client()
            .table("chat_sessions")
            .update(
                {
                    "title": payload.title or "New chat",
                    "preview": payload.preview,
                    "messages": message_payload,
                    "updated_at": current_timestamp(),
                }
            )
            .eq("id", chat_id)
            .eq("client_id", payload.client_id)
            .execute()
        )
        return response.data[0] if response.data else None

    return get_local_chat_store().update(
        chat_id,
        client_id=payload.client_id,
        title=payload.title,
        preview=payload.preview,
        messages=message_payload,
    )


def delete_chat_record(chat_id: str, client_id: str) -> dict | None:
    if has_supabase_chat_store():
        response = (
            get_supabase_client()
            .table("chat_sessions")
            .delete()
            .eq("id", chat_id)
            .eq("client_id", client_id)
            .execute()
        )
        return response.data[0] if response.data else None

    return get_local_chat_store().delete(chat_id, client_id)


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
        "chat_storage": "supabase" if has_supabase_chat_store() else "local",
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
        if not (provider_key or any_provider_key_present()):
            raise ValueError("API Key not found. Please provide one or set it in .env")

        user_id, user_key = user
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
    except Exception as e:
        print(f"Chat Endpoint Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    """Reserved post-turn mutation seam until chat-thread writes land in StateStore."""
    assert ctx.session_id is not None
    async with session_locks.lock(ctx.session_id):
        # chat_threads has no StateStore upsert yet; retain the lock/defer seam without
        # inventing a persistence API. A future upsert belongs at this exact point.
        print(f"[turn:{ctx.user_key}] deferred session work for {ctx.session_id}")


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


@app.post("/v1/keys")
async def create_key(
    payload: KeyInput,
    user: tuple[str, str] = Depends(current_user),
):
    user_id, _ = user
    raw_key, key_hash = generate_api_key()
    row = await state_store.create_api_key(user_id, key_hash, label=payload.label)
    return {"id": row["id"], "api_key": raw_key, "label": payload.label}


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


@app.put("/v1/projects/{project_id}/config")
async def update_config(
    project_id: str,
    payload: ConfigInput,
    user: tuple[str, str] = Depends(current_user),
):
    user_id, _ = user
    if await state_store.get_project(user_id, project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
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
    runtime_cache.invalidate(project_id)
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
def list_sources():
    """List all uploaded source documents."""
    sources = get_default_archives().list_sources()
    return {"sources": sources, "count": len(sources)}


@app.delete("/v1/sources/{filename}")
async def delete_source(filename: str, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    """Delete a source document."""
    archives = get_archives(x_api_key)
    safe_name = os.path.basename(filename)
    file_path = str(archives.data_dir / safe_name)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        os.remove(file_path)
        index_metadata = await archives.remove_file(safe_name)

        return {
            "success": True,
            "message": f"File '{safe_name}' deleted.",
            "index_metadata": index_metadata,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/chats")
def list_chats(client_id: str):
    try:
        sessions = [
            serialize_session_summary(record).model_dump()
            for record in list_chat_records(client_id)
        ]
        return {"sessions": sessions, "count": len(sessions)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/chats/{chat_id}", response_model=ChatSessionDetail)
def get_chat(chat_id: str, client_id: str):
    try:
        record = get_chat_record(chat_id, client_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Chat not found")
        return serialize_session_detail(record)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/chats", response_model=ChatSessionDetail)
def create_chat(payload: ChatSessionPayload):
    try:
        record = create_chat_record(payload)
        return serialize_session_detail(record)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/v1/chats/{chat_id}", response_model=ChatSessionDetail)
def update_chat(chat_id: str, payload: ChatSessionPayload):
    try:
        record = update_chat_record(chat_id, payload)
        if record is None:
            raise HTTPException(status_code=404, detail="Chat not found")
        return serialize_session_detail(record)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/v1/chats/{chat_id}")
def delete_chat(chat_id: str, client_id: str):
    try:
        record = delete_chat_record(chat_id, client_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Chat not found")
        return {"success": True, "message": "Chat deleted."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
