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
from typing import Any, Iterator, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

_ROLE_TO_MESSAGE = {
    "system": SystemMessage,
    "user": HumanMessage,
    "assistant": AIMessage,
}


class OpenAIMessage(BaseModel):
    role: str
    content: Optional[str] = ""


class ChatCompletionRequest(BaseModel):
    messages: list[OpenAIMessage]
    model: Optional[str] = None
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


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


def format_lore(chunks: list[tuple[Any, float | None]]) -> str:
    lines: list[str] = []
    for document, _score in chunks:
        source = document.metadata.get("source", "unknown")
        lines.append(f"- ({source}) {document.page_content.strip()}")
    return "\n".join(lines)


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


def stream_completion(llm: Any, messages: list[BaseMessage], model: str) -> Iterator[str]:
    """Yield Server-Sent Events in OpenAI's streaming chunk format."""
    completion_id = _completion_id()
    created = int(time.time())

    def chunk(delta: dict[str, Any], finish_reason: Optional[str] = None) -> str:
        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        return f"data: {json.dumps(payload)}\n\n"

    yield chunk({"role": "assistant"})
    for piece in llm.stream(messages):
        content = piece.content
        if content:
            yield chunk({"content": content})
    yield chunk({}, finish_reason="stop")
    yield "data: [DONE]\n\n"
