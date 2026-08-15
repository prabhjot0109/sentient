"""Request bodies for the project routes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from sentient.core.config import Provider, SearchType


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    base_preset: str = Field(default="custom", min_length=1, max_length=100)


class ProjectRenameInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm_provider: Provider | None = None
    embedding_provider: Provider | None = None
    model_name: str | None = None
    embedding_model_name: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)
    mrl_vector_size: int | None = Field(default=None, ge=1)
    reasoning_effort: str | None = None
    reasoning_format: str | None = None
    rag_search_type: SearchType | None = None
    rag_top_k: int | None = Field(default=None, ge=1)
    rag_fetch_k: int | None = Field(default=None, ge=1)
    rag_mmr_lambda: float | None = Field(default=None, ge=0, le=1)
    rag_score_threshold: float | None = Field(default=None, ge=0, le=1)
    rag_chunk_size: int | None = Field(default=None, ge=1)
    rag_chunk_overlap: int | None = Field(default=None, ge=0)
    persona_prompt: str | None = None
    history_window: int | None = Field(default=None, ge=1)


class PersonaInput(BaseModel):
    system_prompt: str
