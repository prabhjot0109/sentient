"""Request bodies for the project routes."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from sentient.core.config import Provider, SearchType


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    base_preset: str = Field(default="custom", min_length=1, max_length=100)


class ProjectRenameInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm_provider: Optional[Provider] = None
    embedding_provider: Optional[Provider] = None
    model_name: Optional[str] = None
    embedding_model_name: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    mrl_vector_size: Optional[int] = Field(default=None, ge=1)
    reasoning_effort: Optional[str] = None
    reasoning_format: Optional[str] = None
    rag_search_type: Optional[SearchType] = None
    rag_top_k: Optional[int] = Field(default=None, ge=1)
    rag_fetch_k: Optional[int] = Field(default=None, ge=1)
    rag_mmr_lambda: Optional[float] = Field(default=None, ge=0, le=1)
    rag_score_threshold: Optional[float] = Field(default=None, ge=0, le=1)
    rag_chunk_size: Optional[int] = Field(default=None, ge=1)
    rag_chunk_overlap: Optional[int] = Field(default=None, ge=0)
    persona_prompt: Optional[str] = None
    history_window: Optional[int] = Field(default=None, ge=1)


class PersonaInput(BaseModel):
    system_prompt: str
