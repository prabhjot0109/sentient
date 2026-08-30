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
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any
from uuid import uuid4

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
from sentient.core.logging import get_logger
from sentient.services.condense import condense_query
from sentient.services.runtime import embedding_signature
from sentient.services.usage import TokenUsage, usage_of

log = get_logger(__name__)


# The fields a transcript renders. The full `metadata` blob is deliberately not
# among them: it carries the tenant key, the project id and the embedding
# signature, which are routing internals, and it would be duplicated onto every
# stored chunk of every turn forever.
_PERSISTED_CHUNK_FIELDS = ("content", "score", "source", "page_label", "chunk_id")


@dataclass(frozen=True)
class Grounding:
    """What retrieval produced for one turn.

    `error` exists because the alternative is what shipped: retrieval is
    best-effort, so a failure returned an empty list and the turn answered from
    the persona alone. An empty list and a failed lookup then looked identical to
    every consumer, and a Qdrant cluster refusing every filtered query for want
    of a payload index read to the player as an NPC with nothing to say. The two
    are different sentences and the console has to be able to tell them apart.
    """

    sources: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    #: The project's documents were embedded under a different signature than the
    #: one this turn queried with, and nothing matched. Set only when both hold,
    #: because a project that still returns chunks is not worth alarming about.
    stale_index: bool = False

    def persistable(self) -> list[dict[str, Any]] | None:
        """The rows to store on the assistant message, or None when unknown.

        None when the lookup failed: the turn's provenance is genuinely unknown,
        and recording `[]` would claim retrieval ran and matched nothing.
        """
        if self.error is not None:
            return None
        return [{k: chunk.get(k) for k in _PERSISTED_CHUNK_FIELDS} for chunk in self.sources]


def _as_sources(chunks: list) -> list[dict[str, Any]]:
    """The wire shape for retrieved chunks, built once for both chat surfaces."""
    return [
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


def assert_retrievable(ctx) -> None:
    """Raise if this project's vectors are mid-rebuild.

    One function, three call sites. It used to be two inline copies that
    disagreed on whether to test `project_id`, and the third path -- /v1/retrieve
    -- had no copy at all, so a lore search during a reindex returned 200 with an
    empty chunk list. "There is no lore" and "the lore is being re-embedded" are
    different sentences and the console has to be able to tell them apart.
    """
    if ctx.project_id and ctx.status == "reindexing_required":
        raise ReindexInProgress("project is reindexing; retrieval temporarily unavailable")


async def _ground_project_turn(
    ctx,
    history,
    message: str,
    top_k: int | None,
    *,
    get_archives,
    get_llm,
    stored_signature: str | None = None,
) -> tuple[Any, list, Grounding]:
    """Everything both renderers of a web turn need: model, prompt, grounding.

    Factored out rather than duplicated. F8 existed as a backlog item precisely
    because the two chat surfaces each re-implemented this once before, and one
    of them then got streaming while the other did not.
    """
    assert_retrievable(ctx)

    async def _retrieve() -> tuple[list, str | None]:
        try:
            archives = await get_archives(ctx)
            chunks = await archives.retrieve(
                message,
                k=top_k or ctx.rag_settings["top_k"],
                search_type=ctx.rag_settings["search_type"],
                min_score=ctx.rag_settings["score_threshold"],
                user_key=ctx.user_key,
                project_id=ctx.project_id,
                embedding_signature=embedding_signature(ctx.rag_settings),
            )
            return chunks, None
        except Exception as exc:
            # Grounding is best-effort: a retrieval failure degrades the answer,
            # it does not fail the turn. It is REPORTED rather than swallowed,
            # though -- see Grounding.error.
            log.warning("retrieval failed; answering ungrounded", exc_info=True)
            return [], f"{type(exc).__name__}: {exc}"[:400]

    llm, (chunks, retrieval_error) = await asyncio.gather(get_llm(ctx), _retrieve())
    turn_messages = [OpenAIMessage(role=row["role"], content=row["content"]) for row in history]
    turn_messages.append(OpenAIMessage(role="user", content=message))
    messages = inject_persona(to_langchain(turn_messages), ctx.system_prompt)
    messages = inject_lore(messages, format_lore(chunks))
    # The game path has logged this since R5; the console path had no equivalent,
    # so "the NPC ignored my lore" could only be diagnosed by reproducing it. One
    # line answers whether retrieval ran, how much it found, and under which
    # signature -- a mismatch there returns zero chunks and raises nothing.
    signature = embedding_signature(ctx.rag_settings)
    log.info(
        "lore retrieved",
        extra={
            "chunks": len(chunks),
            "signature": signature,
            "stored_signature": stored_signature,
            "retrieval_error": retrieval_error,
        },
    )
    return (
        llm,
        messages,
        Grounding(
            sources=_as_sources(chunks),
            error=retrieval_error,
            stale_index=(
                not chunks
                and retrieval_error is None
                and stored_signature is not None
                and stored_signature != signature
            ),
        ),
    )


async def run_project_turn(
    ctx,
    history,
    message: str,
    top_k: int | None,
    *,
    get_archives,
    get_llm,
    stored_signature: str | None = None,
) -> dict[str, Any]:
    """Generate a project web turn with bounded durable history before the new turn."""
    llm, messages, grounding = await _ground_project_turn(
        ctx,
        history,
        message,
        top_k,
        get_archives=get_archives,
        get_llm=get_llm,
        stored_signature=stored_signature,
    )
    result = await llm.ainvoke(messages)
    return {
        "answer": str(result.content),
        "grounding": grounding,
        "top_k": top_k or ctx.rag_settings["top_k"],
        "usage": usage_of(result, ctx.llm_settings["model"]),
    }


async def stream_project_turn(
    ctx,
    history,
    message: str,
    top_k: int | None,
    thread_id: str,
    *,
    get_archives,
    get_llm,
    on_complete,
    stored_signature: str | None = None,
) -> AsyncIterator[str]:
    """Render a web turn as SSE.

    Grounding is awaited HERE rather than inside the returned generator, so a
    `ReindexInProgress` still reaches the router as a 409. Raised from inside the
    generator it would arrive after the response had started and the client would
    see a broken stream instead of a status code.

    The first frame is a `sentient.chat.meta` object carrying the thread id and
    the retrieved sources — the two things `ChatResponse` returns that cannot be
    appended after the stream, because the client renders as it reads. Consumers
    dispatch on `object`, so any frame that is not a `chat.completion.chunk` is
    skipped, which is also what makes the error frame and future metadata frames
    free to add.
    """
    llm, messages, grounding = await _ground_project_turn(
        ctx,
        history,
        message,
        top_k,
        get_archives=get_archives,
        get_llm=get_llm,
        stored_signature=stored_signature,
    )
    meta = json.dumps(
        {
            "object": "sentient.chat.meta",
            "thread_id": thread_id,
            "sources": grounding.sources,
            "retrieval_error": grounding.error,
            "stale_index": grounding.stale_index,
            "top_k": top_k or ctx.rag_settings["top_k"],
        }
    )

    async def _frames() -> AsyncIterator[str]:
        yield f"data: {meta}\n\n"
        # `stream_completion`'s callback stays (reply, usage): the game path
        # shares it and grounds itself differently. The chunks are closed over
        # here instead, the one place that has both them and the finished reply.
        async for event in stream_completion(
            llm,
            messages,
            ctx.llm_settings["model"],
            on_complete=lambda reply, usage: on_complete(reply, usage, grounding),
        ):
            yield event

    return _frames()


async def store_thread_turn(
    state_store,
    session_locks,
    thread_id: str,
    message: str,
    reply: str,
    usage: TokenUsage,
    grounding: Grounding | None = None,
) -> None:
    """Append the user line and the reply under the thread's lock.

    The lock is per-thread, not global: two turns on the same thread must not
    interleave their writes, but turns on different threads are independent.

    Usage lands on the assistant row only. A user message consumed no tokens of
    its own; the prompt count for the turn belongs to the completion that read it.
    """
    async with session_locks.lock(thread_id):
        await state_store.add_message(thread_id, "user", message)
        await state_store.add_message(
            thread_id,
            "assistant",
            reply,
            **usage.as_kwargs(),
            sources=None if grounding is None else grounding.persistable(),
        )


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

    Returns `(llm, messages, model_name, grounding)`. The caller decides how to
    render the result — streamed SSE or a single completion body — which is what makes
    both chat surfaces renderers over one call.
    """
    assert_retrievable(ctx)

    model_name = ctx.llm_settings["model"]
    query = last_user_text(request.messages)
    log.info(
        "turn started",
        extra={
            "provider": ctx.llm_settings["provider"],
            "model": model_name,
            "stream": request.stream,
            "query": query.strip(),
        },
    )

    errors: list[str] = []

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
        except Exception as exc:
            log.warning("retrieval failed; answering ungrounded", exc_info=True)
            errors.append(f"{type(exc).__name__}: {exc}"[:400])
            return []

    ground_started = perf_counter()
    if settings.condense_queries and query.strip():
        llm, archives = await asyncio.gather(get_llm(ctx), get_archives(ctx))
        retrieval_query = await condense_query(llm, to_history(request.messages), query)
        if retrieval_query != query:
            log.info(
                "query condensed",
                extra={"query": query.strip(), "condensed": retrieval_query.strip()},
            )
        chunks = await _retrieve(retrieval_query, archives)
    else:
        llm, chunks = await asyncio.gather(get_llm(ctx), _retrieve(query))
    ground_ms = (perf_counter() - ground_started) * 1000

    log.info("lore retrieved", extra={"chunks": len(chunks)})
    prompt_started = perf_counter()
    messages = inject_persona(to_langchain(request.messages), ctx.system_prompt)
    messages = inject_lore(messages, format_lore(chunks))
    prompt_ms = (perf_counter() - prompt_started) * 1000
    log.info(
        "prompt built",
        extra={
            "context_ms": round(context_ms, 1),
            "ground_ms": round(ground_ms, 1),
            "prompt_ms": round(prompt_ms, 1),
        },
    )
    return (
        llm,
        messages,
        model_name,
        Grounding(sources=_as_sources(chunks), error=errors[0] if errors else None),
    )


async def stream_completion(llm, messages, model_name: str, *, on_complete):
    """Keep the response path lock-free; queue post-turn work after streaming ends.

    `on_complete(reply, usage)` runs after the last token. If the client
    disconnects mid-stream `astream_completion` never reaches its sink, so the
    callback gets ("", an empty usage) — callers must treat an empty reply as
    "nothing worth persisting", not as a valid turn.
    """
    captured: list[tuple[str, TokenUsage]] = []

    def _sink(text: str, usage_chunk) -> None:
        captured.append((text, usage_of(usage_chunk, model_name)))

    try:
        async for event in astream_completion(llm, messages, model_name, on_reply=_sink):
            yield event
    finally:
        reply, usage = captured[0] if captured else ("", TokenUsage(model_name))
        on_complete(reply, usage)


async def record_game_turn(
    ctx,
    messages: list[OpenAIMessage],
    reply: str,
    usage: TokenUsage,
    *,
    state_store,
    session_locks,
    grounding: Grounding | None = None,
) -> None:
    """Persist both sides of an in-game turn so the console can replay it.

    Runs entirely inside `defer()`, after the response has been rendered — nothing
    here is on the time-to-first-token path.

    Thread identity comes from `ctx.session_id` when the client sends one, and
    otherwise from the conversation prefix (see `conversation_prefix_hash`).
    Accepted limitations, stated rather than hidden:

    - Mantella summarises long conversations into its own local files and then
      sends a shortened history. The prefix stops matching and a new thread
      begins. That is the correct outcome — the model's context genuinely
      restarted — but the console shows two threads for what the player
      experienced as one.
    - A retried turn arrives with a prefix the previous attempt already advanced
      past, so it opens a new thread rather than appending. Deduplicating instead
      would mean an empty prefix could match an existing thread, which would merge
      two NPCs' opening lines — the worse of the two failures.
    - `npc_name` is only available when the client sends it, so threads are
      otherwise titled from the first player line.
    """
    if not ctx.project_id:
        # Loud, because this is the whole of "why are my in-game conversations
        # not in the console?". Mantella's `llm_api` defaults to the bare `/v1`
        # form, which resolves no project, so every turn is dropped here and the
        # player sees a working game with an empty console and no error anywhere.
        # Name the fix in the message: a reader who has to open this file to find
        # out what to change has already been failed by the log line.
        log.warning(
            "in-game turn not persisted: the request resolved no project. Point "
            "Mantella's llm_api at /v1/<api_key>/<project_id> rather than /v1.",
        )
        return
    if not reply.strip():
        return

    user_text = last_user_text(messages)
    if not user_text.strip():
        return

    incoming = conversation_prefix_hash(messages)
    outgoing = conversation_prefix_hash_after(messages, reply)

    # Lock on the conversation, not the project: two concurrent turns of the SAME
    # conversation arrive with the same incoming hash and must not fork it, while
    # two different NPCs' turns are independent and must not serialise.
    async with session_locks.lock(f"{ctx.project_id}:{incoming or 'new'}"):
        thread = None
        if ctx.session_id:
            thread = await state_store.upsert_thread(
                ctx.project_id, ctx.session_id, npc_name=ctx.npc_name
            )
        elif incoming:
            thread = await state_store.get_thread_by_prefix(ctx.project_id, incoming)

        if thread is None:
            thread = await state_store.upsert_thread(
                ctx.project_id,
                uuid4().hex,
                npc_name=ctx.npc_name,
                title=(ctx.npc_name or user_text.strip())[:60] or "In-game conversation",
            )

        await state_store.add_message(thread["id"], "user", user_text)
        await state_store.add_message(
            thread["id"],
            "assistant",
            reply,
            **usage.as_kwargs(),
            sources=None if grounding is None else grounding.persistable(),
        )
        await state_store.set_thread_prefix(thread["id"], outgoing)
