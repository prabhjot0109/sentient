"""Grounded generation — the one operation both chat surfaces are built on.

`/v1/chat` (the web UI) and `/v1/chat/completions` (Mantella) used to
re-implement the same idea separately in `api.py`, which is why R5's streaming
support landed on one and not the other. Backlog item F8 is a symptom of that
duplication, not an independent feature.

R9 does not implement F8. It removes the structural reason F8 was needed: once
this module owns the generate step, the two routes are two renderers over one
call, and adding streaming to `/v1/chat` becomes a rendering change rather than
a re-implementation.

Collaborators (`get_archives`, `get_llm`, the state store, the lock table)
arrive as arguments — `services/` may not import `api.deps`.
"""

from __future__ import annotations

import asyncio
import hashlib
from time import perf_counter
from typing import Any

from sentient.adapters.llm.openai_wire import (
    OpenAIMessage,
    astream_completion,
    format_lore,
    inject_lore,
    inject_persona,
    last_user_text,
    to_history,
    to_langchain,
)
from sentient.core.errors import ReindexInProgress
from sentient.services.condense import condense_query
from sentient.services.runtime import embedding_signature


def _hash_pairs(pairs: list[tuple[str, str]]) -> str:
    """One encoding, used by both hash functions so they cannot drift apart.

    The 0x1f unit separator between role and content is not decoration: a plain
    concatenation lets ("user", "ab") and ("user", "a") + ("", "b") collide, which
    would silently merge two different conversations into one thread.
    """
    payload = "\n".join(f"{role}\x1f{content}" for role, content in pairs)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _transcript_pairs(messages: list[OpenAIMessage]) -> list[tuple[str, str]]:
    """Non-system messages as (role, content). The system prompt is excluded on
    purpose: it carries the persona, which the user may edit between turns, and a
    persona edit must not fork an in-progress conversation."""
    return [(m.role, m.content or "") for m in messages if m.role != "system"]


def conversation_prefix_hash(messages: list[OpenAIMessage]) -> str | None:
    """Hash the conversation as it stood BEFORE this turn's user line.

    Mantella sends no session_id but re-sends the whole conversation every turn,
    so the transcript already stored equals the incoming payload minus the system
    message and minus the final user turn. Hashing that identifies the thread with
    no client change.

    Returns None when the slice is empty — a first turn. An empty prefix must NEVER
    match an existing thread; that is what makes a turn-1 collision between two
    different NPCs impossible.
    """
    pairs = _transcript_pairs(messages)
    for i in range(len(pairs) - 1, -1, -1):
        if pairs[i][0] == "user":
            pairs = pairs[:i]
            break
    if not pairs:
        return None
    return _hash_pairs(pairs)


def conversation_prefix_hash_after(messages: list[OpenAIMessage], reply: str) -> str:
    """The hash the NEXT turn will arrive with: this payload plus the reply."""
    return _hash_pairs([*_transcript_pairs(messages), ("assistant", reply)])


async def run_project_turn(
    ctx,
    history,
    message: str,
    top_k: int | None,
    *,
    get_archives,
    get_llm,
) -> dict[str, Any]:
    """Generate a project web turn with bounded durable history before the new turn."""
    if ctx.status == "reindexing_required":
        raise ReindexInProgress("project is reindexing; retrieval temporarily unavailable")

    async def _retrieve():
        try:
            archives = await get_archives(ctx)
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
            # Grounding is best-effort: a retrieval failure degrades the answer,
            # it does not fail the turn.
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
    return {
        "answer": str(result.content),
        "sources": sources,
        "top_k": top_k or ctx.rag_settings["top_k"],
    }


async def store_thread_turn(
    state_store,
    session_locks,
    thread_id: str,
    message: str,
    reply: str,
) -> None:
    """Append the user line and the reply under the thread's lock.

    The lock is per-thread, not global: two turns on the same thread must not
    interleave their writes, but turns on different threads are independent.
    """
    async with session_locks.lock(thread_id):
        await state_store.add_message(thread_id, "user", message)
        await state_store.add_message(thread_id, "assistant", reply)


async def prepare_completion(
    request,
    ctx,
    *,
    settings,
    get_llm,
    get_archives,
    context_ms: float = 0.0,
):
    """Resolve the model and build the grounded prompt for an OpenAI-wire turn.

    Returns `(llm, messages, model_name)`. The caller decides how to render the
    result — streamed SSE or a single completion body — which is what makes
    both chat surfaces renderers over one call.
    """
    if ctx.project_id and ctx.status == "reindexing_required":
        raise ReindexInProgress("project is reindexing; retrieval temporarily unavailable")

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
            resolved_archives = archives or await get_archives(ctx)
            search_type = ctx.rag_settings["search_type"] if ctx.project_id else "similarity"
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
    if settings.condense_queries and query.strip():
        llm, archives = await asyncio.gather(get_llm(ctx), get_archives(ctx))
        retrieval_query = await condense_query(llm, to_history(request.messages), query)
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
    return llm, messages, model_name


async def stream_completion(llm, messages, model_name: str, *, on_complete):
    """Keep the response path lock-free; queue post-turn work after streaming ends.

    `on_complete` receives the full reply text. If the client disconnects mid-stream
    `astream_completion` never reaches its sink, so the callback gets "" — callers
    must treat an empty reply as "nothing worth persisting", not as a valid turn.
    """
    captured: list[str] = []
    try:
        async for event in astream_completion(llm, messages, model_name, on_reply=captured.append):
            yield event
    finally:
        on_complete("".join(captured))


async def record_game_turn(ctx, *, state_store, session_locks) -> None:
    """Surface game sessions in the sidebar. Write-only: the game path never reads
    server-side memory — Mantella carries the conversation in its own payload."""
    assert ctx.session_id is not None
    async with session_locks.lock(ctx.session_id):
        await state_store.upsert_thread(ctx.project_id, ctx.session_id, npc_name=ctx.npc_name)
