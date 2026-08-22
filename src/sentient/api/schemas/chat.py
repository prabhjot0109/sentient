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


class ChatResponse(BaseModel):
    response: str
    success: bool
    sources: list[RetrievedChunk] = Field(default_factory=list)
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
