"""Request and response bodies for the web chat and retrieval routes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    content: str
    score: float | None = None
    source: str
    page_label: str = ""
    chunk_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatInput(BaseModel):
    message: str
    api_key: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    project_id: str | None = None
    thread_id: str | None = None
    # Absent or False renders the ChatResponse body below, byte for byte.
    # True renders SSE through the same encoder as /v1/chat/completions.
    stream: bool = False


class ChatResponse(BaseModel):
    response: str
    success: bool
    sources: list[RetrievedChunk] = Field(default_factory=list)
    # Set when the lore lookup itself failed, which is NOT the same as matching
    # nothing: the reply came from the persona alone and the client must be able
    # to say so rather than showing an empty source list.
    retrieval_error: str | None = None
    # True when the lookup ran cleanly, matched nothing, and the project's
    # documents were embedded under a different signature than the one queried.
    # That combination is not "no lore": it is lore this deployment can no longer
    # reach, and the only fix is a reindex.
    stale_index: bool = False
    top_k: int | None = None
    retrieval_ms: float | None = None
    thread_id: str | None = None


class RetrievalInput(BaseModel):
    query: str
    # A PROVIDER credential only (Google/Groq/...), used to build the embedding
    # client. Caller identity comes from the Authorization or X-API-Key header;
    # this field never selects a tenant. It used to, which made the route open.
    api_key: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    project_id: str | None = None


class RetrievalResponse(BaseModel):
    success: bool
    query: str
    top_k: int
    retrieval_ms: float
    chunks: list[RetrievedChunk] = Field(default_factory=list)
