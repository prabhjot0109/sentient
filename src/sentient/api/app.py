from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager
from dataclasses import replace
from time import perf_counter
from typing import Any, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from sentient.adapters.auth import AuthError, resolve_user
from sentient.adapters.llm.openai_wire import (
    ChatCompletionRequest,
    OpenAIMessage,
    astream_completion,
    build_completion_response,
    format_lore,
    inject_lore,
    inject_persona,
    last_user_text,
    to_history,
    to_langchain,
)
from sentient.api import deps
from sentient.api.routers import (
    audio,
    chat,
    credentials,
    documents,
    health,
    keys,
    projects,
    threads,
)
from sentient.core.concurrency import defer
from sentient.core.config import load_rag_settings
from sentient.services.condense import condense_query
from sentient.services.runtime import (
    RuntimeContext,
    embedding_signature,
    resolve_runtime_context,
)

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
    await deps.get_default_archives().retrieve(
        "warmup", k=1, search_type="similarity", min_score=0.0
    )
    print(f"[WARMUP] Lore path ready in {perf_counter() - started:.1f}s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start process-local workers and drain accepted work during shutdown."""
    await deps.ingest_queue.start()
    await deps.reindex_queue.start()
    try:
        have_provider_key = deps.any_provider_key_present()
        try:
            if have_provider_key:
                # Build the on-disk index from data/ at boot if missing, so the Mantella
                # completions path has lore to ground on. Async so startup embedding
                # never blocks the event loop. No global brain — clients resolve per turn.
                await deps.get_default_archives().ensure_index()
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
        await deps.reindex_queue.stop()
        await deps.ingest_queue.stop()
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
    allow_origins=list(deps._settings.cors_allow_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(keys.router)
app.include_router(threads.router)
app.include_router(credentials.router)
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(audio.router)
app.include_router(chat.router)


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
            resolved_archives = archives or await deps.get_archives_for_context(ctx)
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
    if deps._settings.condense_queries and query.strip():
        llm, archives = await asyncio.gather(
            deps.get_llm(ctx), deps.get_archives_for_context(ctx)
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
        llm, chunks = await asyncio.gather(deps.get_llm(ctx), _retrieve(query))
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
    async with deps.session_locks.lock(ctx.session_id):
        await deps.state_store.upsert_thread(ctx.project_id, ctx.session_id, npc_name=ctx.npc_name)


def _schedule_deferred_turn_work(ctx: RuntimeContext) -> None:
    if ctx.session_id and ctx.project_id:
        defer(_deferred_turn_work(ctx), label="session-turn")


@app.post("/v1/chat/completions")
async def openai_chat_completions(
    request: ChatCompletionRequest,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """OpenAI-compatible env-default route retained for existing clients."""
    try:
        context_started = perf_counter()
        ctx = await deps.completions_ctx(x_api_key, None)
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
    ctx = await deps.completions_ctx(api_key, None)
    context_ms = (perf_counter() - context_started) * 1000
    return await _run_completions(request, ctx, context_ms=context_ms)


@app.post("/v1/{api_key}/{project_id}/chat/completions")
async def openai_chat_completions_project(
    api_key: str,
    project_id: str,
    request: ChatCompletionRequest,
):
    context_started = perf_counter()
    ctx = await deps.completions_ctx(api_key, project_id)
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
