"""The OpenAI-compatible surface: `/v1/chat/completions` in all three path
shapes, plus `/v1/models`.

Three shapes exist because Mantella cannot send headers: it puts the key, and
optionally the project, in the URL. The env-default shape is kept for older
clients.

Error translation, preserved exactly from the pre-R9 route bodies:

    ReindexInProgress -> 409 "project is reindexing; retrieval temporarily unavailable"

Identity failures (401) and project-ownership failures (403) are raised by
`deps.completions_ctx`, which still speaks HTTP directly.
"""

from __future__ import annotations

import time
from dataclasses import replace
from time import perf_counter

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from sentient.adapters.llm.openai_wire import (
    ChatCompletionRequest,
    build_completion_response,
)
from sentient.api import deps
from sentient.core.concurrency import defer
from sentient.core.config import load_rag_settings
from sentient.core.errors import ReindexInProgress
from sentient.services import chat as service
from sentient.services.usage import TokenUsage, usage_of

router = APIRouter()


def _schedule_deferred_turn_work(ctx, request, reply: str, usage: TokenUsage) -> None:
    """Queue the transcript write. Requires only a project — B2's session_id
    requirement is gone, because Mantella never sent one and the thread is now
    identified from the payload itself."""
    if not ctx.project_id:
        return
    defer(
        service.record_game_turn(
            ctx,
            request.messages,
            reply,
            usage,
            state_store=deps.state_store,
            session_locks=deps.session_locks,
        ),
        label="game-turn",
    )


async def _stream_with_deferred_turn_work(llm, messages, model_name, ctx, request):
    """Keep the response path lock-free; queue post-turn work after streaming ends."""
    async for event in service.stream_completion(
        llm,
        messages,
        model_name,
        on_complete=lambda reply, usage: _schedule_deferred_turn_work(ctx, request, reply, usage),
    ):
        yield event


async def _run_completions(
    request: ChatCompletionRequest,
    ctx,
    *,
    context_ms: float = 0.0,
):
    """Render one grounded turn as SSE or as a single completion body."""
    try:
        llm, messages, model_name = await service.prepare_completion(
            request,
            ctx,
            settings=deps._settings,
            get_llm=deps.get_llm,
            get_archives=deps.get_archives_for_context,
            context_ms=context_ms,
        )
    except ReindexInProgress as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    if request.stream:
        print(f"[Mantella:{ctx.user_key}]   << streaming reply")
        return StreamingResponse(
            _stream_with_deferred_turn_work(llm, messages, model_name, ctx, request),
            media_type="text/event-stream",
        )

    result = await llm.ainvoke(messages)
    reply = str(result.content)
    print(f"[Mantella:{ctx.user_key}]   << reply ({len(reply)} chars): {reply!r}")
    _schedule_deferred_turn_work(ctx, request, reply, usage_of(result, model_name))
    return build_completion_response(reply, model_name)


@router.post("/v1/chat/completions")
async def openai_chat_completions(
    request: ChatCompletionRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
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


@router.post("/v1/{api_key}/chat/completions")
async def openai_chat_completions_key(
    api_key: str,
    request: ChatCompletionRequest,
):
    context_started = perf_counter()
    ctx = await deps.completions_ctx(api_key, None)
    context_ms = (perf_counter() - context_started) * 1000
    return await _run_completions(request, ctx, context_ms=context_ms)


@router.post("/v1/{api_key}/{project_id}/chat/completions")
async def openai_chat_completions_project(
    api_key: str,
    project_id: str,
    request: ChatCompletionRequest,
):
    context_started = perf_counter()
    ctx = await deps.completions_ctx(api_key, project_id)
    if request.session_id or request.npc_name:
        ctx = replace(ctx, session_id=request.session_id, npc_name=request.npc_name)
    context_ms = (perf_counter() - context_started) * 1000
    return await _run_completions(request, ctx, context_ms=context_ms)


@router.get("/v1/models")
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
