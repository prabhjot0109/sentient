"""OpenAI-compatible chat-completions adapter.

This exposes the RAG engine as an OpenAI `/v1/chat/completions` endpoint so that
external clients which speak the OpenAI API (e.g. the Mantella Skyrim mod) can use
Sentient as their LLM backend.

The contract is deliberately different from the standalone Sentinel app:
the caller (Mantella) owns the NPC persona and conversation memory, while Sentient
only grounds the reply in retrieved lore. Retrieved lore is *appended* to the
caller's system prompt (augment, never gate), so NPCs stay in character and keep
talking even when nothing relevant is found.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from sentient.adapters.tracing import trace_config
from sentient.core.logging import get_logger

log = get_logger(__name__)

_ROLE_TO_MESSAGE = {
    "system": SystemMessage,
    "user": HumanMessage,
    "assistant": AIMessage,
}


class OpenAIMessage(BaseModel):
    role: str
    content: str | None = ""


class ChatCompletionRequest(BaseModel):
    messages: list[OpenAIMessage]
    model: str | None = None
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    session_id: str | None = None
    npc_name: str | None = None


def last_user_text(messages: list[OpenAIMessage]) -> str:
    """The most recent user turn, used as the retrieval query."""
    for message in reversed(messages):
        if message.role == "user":
            return message.content or ""
    return ""


def to_langchain(messages: list[OpenAIMessage]) -> list[BaseMessage]:
    converted: list[BaseMessage] = []
    for message in messages:
        factory = _ROLE_TO_MESSAGE.get(message.role, HumanMessage)
        converted.append(factory(content=message.content or ""))
    return converted


def to_history(messages: list[OpenAIMessage]) -> list[BaseMessage]:
    """All turns except the final user query, as LangChain messages — the context
    condensation needs to resolve pronouns in the latest user turn."""
    last_user_index = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].role == "user":
            last_user_index = i
            break
    kept = messages if last_user_index is None else messages[:last_user_index]
    return to_langchain(kept)


def format_lore(chunks: list[tuple[Any, float | None]]) -> str:
    lines: list[str] = []
    for document, _score in chunks:
        source = document.metadata.get("source", "unknown")
        lines.append(f"- ({source}) {document.page_content.strip()}")
    return "\n".join(lines)


def inject_persona(messages: list[BaseMessage], persona_text: str) -> list[BaseMessage]:
    """Prepend a resolved persona to the system prompt (before retrieved lore).

    No-op when persona_text is empty so callers can pass through unconditionally.
    """
    if not persona_text:
        return messages
    for i, m in enumerate(messages):
        if isinstance(m, SystemMessage):
            messages[i] = SystemMessage(content=f"{persona_text}\n\n{m.content}")
            return messages
    return [SystemMessage(content=persona_text), *messages]


def inject_lore(messages: list[BaseMessage], lore: str) -> list[BaseMessage]:
    """Append retrieved lore to the caller's system prompt, or add one if absent."""
    if not lore:
        return messages

    block = (
        "\n\nRelevant lore retrieved from the Archives. Use it to stay accurate and "
        "in-world. Never mention these notes and never break character. Keep your "
        "reply brief and natural, as in spoken conversation:\n"
        f"{lore}"
    )

    for index, message in enumerate(messages):
        if isinstance(message, SystemMessage):
            messages[index] = SystemMessage(content=str(message.content) + block)
            return messages

    return [SystemMessage(content=block.strip()), *messages]


def _completion_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex}"


# Provider errors can carry a whole HTML error page. The client needs enough to
# tell an outage from a refusal, not the page.
_ERROR_MESSAGE_LIMIT = 500


def error_body(exc: Exception) -> dict[str, Any]:
    """The OpenAI-shaped error payload, unframed.

    The SDK checks any payload for a top-level `error` key and raises on it, so
    the same shape works as a response body (B4, non-streaming) and as an SSE
    frame (H1 Finding 2, streaming). One shape means Mantella needs one
    behaviour, and a player sees the same sentence whichever path they were on.

    `object` is set too, so a consumer that dispatches on `object` — the rule the
    web chat's meta frame introduces — cannot silently drop this one.
    """
    return {
        "object": "error",
        "error": {
            "message": str(exc)[:_ERROR_MESSAGE_LIMIT] or exc.__class__.__name__,
            "type": "provider_error",
            "code": exc.__class__.__name__,
        },
    }


def error_event(exc: Exception) -> str:
    """An SSE frame reporting a failure that happened after HTTP 200 was sent.

    Once the first chunk flushes, no status code can carry the error, so it has
    to travel in-band. The shape is the one the OpenAI SDK already raises on: it
    checks each payload for a top-level `error` key and turns it into an
    `APIError`. Mantella therefore reports an outage with no client change, which
    is the whole point — before this, a dead provider was indistinguishable from
    an NPC with nothing to say.
    """
    return f"data: {json.dumps(error_body(exc))}\n\n"


def build_completion_response(text: str, model: str) -> dict[str, Any]:
    return {
        "id": _completion_id(),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
    }


async def astream_completion(
    llm: Any,
    messages: list[BaseMessage],
    model: str,
    *,
    on_reply: Callable[[str, Any], None] | None = None,
) -> AsyncIterator[str]:
    """Yield OpenAI SSE chunks from LangChain's non-blocking async stream.

    `on_reply(reply, chunk)` is called once, after the last token. `reply` is the
    joined text, which already happens for the log line below; `chunk` is the
    LangChain chunk that carried usage metadata, which the caller interprets —
    `adapters/` cannot import `services/`, and this module has no business
    knowing which field name a given provider uses.

    Both values already exist here, so this costs nothing per token, which is the
    only reason it is done here rather than by re-parsing the SSE frames.

    A provider failure mid-stream ends the stream with `error_event` instead of a
    `finish_reason: "stop"` chunk, then `[DONE]` as usual. `on_reply` still fires,
    with whatever text did arrive.
    """
    completion_id = _completion_id()
    created = int(time.time())

    def chunk(delta: dict[str, Any], finish_reason: str | None = None) -> str:
        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        return f"data: {json.dumps(payload)}\n\n"

    yield chunk({"role": "assistant"})
    started = time.perf_counter()
    first_token_logged = False
    parts: list[str] = []
    last_chunk: Any = None
    usage_chunk: Any = None
    failure: Exception | None = None
    try:
        # `config` is None whenever tracing is off, which is LangChain's own
        # default -- so a fresh clone makes the identical call it made before
        # H8. This is the site that covers BOTH streaming surfaces: the Mantella
        # game route and the console's project chat both arrive here.
        async for piece in llm.astream(messages, config=trace_config()):
            last_chunk = piece
            # Not simply the last chunk: several providers report usage mid-stream and
            # then send a final empty chunk carrying only the finish reason, which
            # would overwrite the counters with nothing. One getattr per chunk.
            if getattr(piece, "usage_metadata", None):
                usage_chunk = piece
            content = piece.content
            if content:
                text = str(content)
                if not first_token_logged:
                    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
                    log.info("first token", extra={"ms": elapsed_ms, "model": model})
                    first_token_logged = True
                parts.append(text)
                yield chunk({"content": text})
    except Exception as exc:
        # Swallowed on purpose. Re-raising aborts the response mid-frame, which is
        # exactly the silence this catch exists to end; the error travels as a
        # frame instead. Not a `finally`: a client disconnect arrives as
        # GeneratorExit, and yielding after that is illegal.
        failure = exc

    reply = "".join(parts)
    if failure is not None:
        log.error(
            "provider stream failed",
            exc_info=failure,
            extra={"model": model, "chars": len(reply)},
        )
        yield error_event(failure)
    else:
        yield chunk({}, finish_reason="stop")
        log.info("streamed reply", extra={"chars": len(reply), "reply": reply})
    yield "data: [DONE]\n\n"
    if on_reply is not None:
        # Partial text is still a real reply: the player heard those tokens, so
        # the transcript keeps them rather than recording the turn as silence.
        on_reply(reply, usage_chunk if usage_chunk is not None else last_chunk)
