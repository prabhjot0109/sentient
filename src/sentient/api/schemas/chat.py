"""Request and response bodies for the web chat and retrieval routes."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    content: str
    score: Optional[float] = None
    source: str
    page_label: str = ""
    chunk_id: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatInput(BaseModel):
    message: str
    api_key: Optional[str] = None
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    project_id: Optional[str] = None
    thread_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    success: bool
    sources: list[RetrievedChunk] = Field(default_factory=list)
    top_k: Optional[int] = None
    retrieval_ms: Optional[float] = None
    thread_id: Optional[str] = None


class RetrievalInput(BaseModel):
    query: str
    api_key: Optional[str] = None
    top_k: Optional[int] = Field(default=None, ge=1, le=20)


class RetrievalResponse(BaseModel):
    success: bool
    query: str
    top_k: int
    retrieval_ms: float
    chunks: list[RetrievedChunk] = Field(default_factory=list)
