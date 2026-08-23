"""The web chat surface: `/v1/chat` and `/v1/retrieve`.

Error translation, preserved exactly from the pre-R9 route bodies:

    ReindexInProgress -> 409 "project is reindexing; retrieval temporarily unavailable"
    (thread_id without project_id) -> 400
    (unknown project / thread)     -> 404
"""

from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from sentient.api import deps
from sentient.api.schemas.chat import (
    ChatInput,
    ChatResponse,
    RetrievalInput,
    RetrievalResponse,
    RetrievedChunk,
)
from sentient.core.concurrency import defer
from sentient.core.errors import ReindexInProgress
from sentient.core.logging import bind, get_logger
from sentient.services import chat as service
from sentient.services.runtime import embedding_signature

log = get_logger(__name__)
router = APIRouter()


@router.post("/v1/chat", response_model=ChatResponse)
async def chat_endpoint(
    payload: ChatInput,
    user: tuple[str, str] = Depends(deps.current_user),
):
    try:
        started_at = perf_counter()
        provider_key = deps._as_provider_key(payload.api_key)
        if not (
            provider_key or deps.any_provider_key_present() or deps._settings.sentient_secret_key
        ):
            raise ValueError("API Key not found. Please provide one or set it in .env")

        user_id, user_key = user
        if payload.thread_id and not payload.project_id:
            raise HTTPException(status_code=400, detail="thread_id requires project_id")
        if payload.stream and not payload.project_id:
            # The projectless path answers through NPCBrain.ask_with_context, which
            # has no streaming twin. A fake single-chunk stream would hide that.
            raise HTTPException(status_code=400, detail="stream requires project_id")

        if payload.project_id:
            project = await deps.state_store.get_project(user_id, payload.project_id)
            if project is None:
                raise HTTPException(status_code=404, detail="project not found")

            bind(project_id=payload.project_id)
            if payload.thread_id:
                thread = await deps.state_store.get_thread(user_id, payload.thread_id)
                if thread is None or thread["project_id"] != payload.project_id:
                    raise HTTPException(status_code=404, detail="thread not found")
            else:
                thread = await deps.state_store.upsert_thread(
                    payload.project_id,
                    uuid4().hex,
                    title=payload.message.strip()[:60] or "New chat",
                )

            ctx = await deps.runtime_cache.resolve(
                deps.state_store,
                deps._settings,
                user_id=user_id,
                user_key=user_key,
                project_id=payload.project_id,
                session_id=thread["id"],
                provider_key=provider_key,
            )
            history_window = (
                await deps.state_store.get_project_config(payload.project_id) or {}
            ).get("history_window") or 20
            bind(thread_id=thread["id"])
            history = await deps.state_store.list_messages(thread["id"], limit=history_window)

            def _persist(reply: str, usage) -> None:
                # An empty reply means the client disconnected before a token
                # arrived, or the provider died first. Neither is a turn.
                if not reply.strip():
                    return
                defer(
                    service.store_thread_turn(
                        deps.state_store,
                        deps.session_locks,
                        thread["id"],
                        payload.message,
                        reply,
                        usage,
                    ),
                    label="thread-memory",
                )

            if payload.stream:
                return StreamingResponse(
                    await service.stream_project_turn(
                        ctx,
                        history,
                        payload.message,
                        payload.top_k,
                        thread["id"],
                        get_archives=deps.get_archives_for_context,
                        get_llm=deps.get_llm,
                        on_complete=_persist,
                    ),
                    media_type="text/event-stream",
                )

            result = await service.run_project_turn(
                ctx,
                history,
                payload.message,
                payload.top_k,
                get_archives=deps.get_archives_for_context,
                get_llm=deps.get_llm,
            )
            _persist(result["answer"], result["usage"])
            elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
            return ChatResponse(
                response=result["answer"],
                success=True,
                sources=[RetrievedChunk(**source) for source in result["sources"]],
                top_k=result["top_k"],
                retrieval_ms=elapsed_ms,
                thread_id=thread["id"],
            )

        ctx = await deps.runtime_cache.resolve(
            deps.state_store,
            deps._settings,
            user_id=user_id,
            user_key=user_key,
            project_id=None,
            session_id=None,
            provider_key=provider_key,
        )
        active_brain = await deps.get_brain(ctx)
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
    except ReindexInProgress as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except HTTPException:
        raise  # ownership/validation statuses must survive the catch-all below
    except Exception as e:
        log.exception("chat endpoint failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/v1/retrieve", response_model=RetrievalResponse)
async def retrieve_endpoint(
    payload: RetrievalInput,
    user: tuple[str, str] = Depends(deps.current_user),
):
    """Raw lore read, scoped to the caller's tenant and project.

    Resolves through `get_archives_for_context` -- the same partition every other
    read and write uses -- rather than the unscoped `get_archives`.
    """
    try:
        started_at = perf_counter()
        user_id, user_key = user
        if payload.project_id and (
            await deps.state_store.get_project(user_id, payload.project_id) is None
        ):
            raise HTTPException(status_code=404, detail="project not found")

        ctx = await deps.runtime_cache.resolve(
            deps.state_store,
            deps._settings,
            user_id=user_id,
            user_key=user_key,
            project_id=payload.project_id,
            session_id=None,
            provider_key=deps._as_provider_key(payload.api_key),
        )
        archives = await deps.get_archives_for_context(ctx)
        chunks = await archives.retrieve(
            payload.query,
            k=payload.top_k or ctx.rag_settings["top_k"],
            search_type=ctx.rag_settings["search_type"],
            min_score=ctx.rag_settings["score_threshold"],
            user_key=ctx.user_key,
            project_id=ctx.project_id,
            embedding_signature=embedding_signature(ctx.rag_settings),
        )
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
            top_k=payload.top_k or ctx.rag_settings["top_k"],
            retrieval_ms=elapsed_ms,
            chunks=serialized_chunks,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
