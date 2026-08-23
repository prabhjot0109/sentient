"""The OpenAI-compatible surface: `/v1/chat/completions` in all three path
shapes, plus `/v1/models`.

Three shapes exist because Mantella cannot send headers: it puts the key, and
optionally the project, in the URL. The env-default shape is kept for older
clients.

Error translation, on all three shapes:

    ReindexInProgress    -> 409 "project is reindexing; retrieval temporarily unavailable"
    a provider raising   -> 502 with an OpenAI-shaped `error_body`
    anything else        -> 500 {"detail": ...}

Identity failures (401) and project-ownership failures (403) are raised by
`deps.completions_ctx`, which still speaks HTTP directly.

The 502 is B4. The two Mantella-shaped routes previously had no handler at all,
so a dead provider escaped to Starlette's `ServerErrorMiddleware` and rendered a
bare text/plain `Internal Server Error` — measured 2026-08-23. The status is not
a pass-through of the upstream's: forwarding a provider's 402 verbatim would
claim that Sentient requires payment.
"""

from __future__ import annotations

import time
from dataclasses import replace
from time import perf_counter

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from sentient.adapters.llm.openai_wire import (
    ChatCompletionRequest,
    build_completion_response,
    error_body,
)
from sentient.api import deps
from sentient.core.concurrency import defer
from sentient.core.config import load_rag_settings
from sentient.core.errors import ReindexInProgress
from sentient.core.logging import get_logger
from sentient.services import chat as service
from sentient.services.usage import TokenUsage, usage_of

log = get_logger(__name__)
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
        log.info("streaming reply")
        return StreamingResponse(
            _stream_with_deferred_turn_work(llm, messages, model_name, ctx, request),
            media_type="text/event-stream",
        )

    try:
        result = await llm.ainvoke(messages)
    except Exception as exc:
        # The streaming path has ended the stream with an OpenAI-shaped `error`
        # frame since 134741e. This is its non-streaming sibling: before it, a
        # dead provider reached Mantella as a bare 500 with an empty body and the
        # player could not tell an outage from an NPC with nothing to say.
        #
        # 502, not a pass-through of the upstream's status: a 402 forwarded
        # verbatim claims that SENTIENT wants payment, which is a different and
        # wrong statement. `core/errors.UpstreamFailure` already documents 502
        # for exactly this.
        log.exception("provider call failed")
        return JSONResponse(status_code=502, content=error_body(exc))

    reply = str(result.content)
    log.info("reply", extra={"chars": len(reply), "reply": reply})
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
        log.exception("chat completions failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/v1/{api_key}/chat/completions")
async def openai_chat_completions_key(
    api_key: str,
    request: ChatCompletionRequest,
):
    try:
        context_started = perf_counter()
        ctx = await deps.completions_ctx(api_key, None)
        context_ms = (perf_counter() - context_started) * 1000
        return await _run_completions(request, ctx, context_ms=context_ms)
    except HTTPException:
        raise
    except Exception as e:
        log.exception("chat completions failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/v1/{api_key}/{project_id}/chat/completions")
async def openai_chat_completions_project(
    api_key: str,
    project_id: str,
    request: ChatCompletionRequest,
):
    try:
        context_started = perf_counter()
        ctx = await deps.completions_ctx(api_key, project_id)
        if request.session_id or request.npc_name:
            ctx = replace(ctx, session_id=request.session_id, npc_name=request.npc_name)
        context_ms = (perf_counter() - context_started) * 1000
        return await _run_completions(request, ctx, context_ms=context_ms)
    except HTTPException:
        raise
    except Exception as e:
        log.exception("chat completions failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


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
