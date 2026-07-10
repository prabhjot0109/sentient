from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from logic.presets import get_preset


@dataclass(frozen=True)
class RuntimeContext:
    user_key: str
    user_id: str | None
    project_id: str | None
    session_id: str | None
    llm_settings: dict[str, Any]
    rag_settings: dict[str, Any]
    system_prompt: str
    config_signature: str


def _floor(settings, provider_key: str | None) -> tuple[dict, dict]:
    """The env-default llm/rag dicts — today's behavior with no project."""
    llm = {
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "base_url": settings.llm_base_url,
        "api_key": provider_key or settings.llm_api_key,
        "temperature": None,
        "max_tokens": None,
        "reasoning_effort": None,
        "reasoning_format": None,
        "timeout": settings.request_timeout,
    }
    rag = {
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "mrl_vector_size": None,
        "search_type": settings.search_type,
        "top_k": settings.top_k,
        "fetch_k": settings.fetch_k,
        "mmr_lambda": settings.lambda_mult,
        "score_threshold": settings.score_threshold,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
    }
    return llm, rag


# project_configs column -> (target dict, key). None values are skipped (floor wins).
_LLM_MAP = {"llm_provider": "provider", "model_name": "model", "temperature": "temperature",
            "max_tokens": "max_tokens", "reasoning_effort": "reasoning_effort",
            "reasoning_format": "reasoning_format"}
_RAG_MAP = {"embedding_provider": "embedding_provider", "embedding_model_name": "embedding_model",
            "mrl_vector_size": "mrl_vector_size", "rag_search_type": "search_type",
            "rag_top_k": "top_k", "rag_fetch_k": "fetch_k", "rag_mmr_lambda": "mmr_lambda",
            "rag_score_threshold": "score_threshold", "rag_chunk_size": "chunk_size",
            "rag_chunk_overlap": "chunk_overlap"}


def _signature(llm: dict, rag: dict) -> str:
    subset = {
        "provider": llm["provider"], "model": llm["model"], "base_url": llm["base_url"],
        "embedding_provider": rag["embedding_provider"], "embedding_model": rag["embedding_model"],
        "mrl_vector_size": rag["mrl_vector_size"],
        # distinguish credentials without leaking them
        "key": hashlib.sha256((llm["api_key"] or "").encode()).hexdigest()[:8],
    }
    return hashlib.sha256(json.dumps(subset, sort_keys=True).encode()).hexdigest()[:24]


async def resolve_runtime_context(state, settings, *, user_id, user_key, project_id=None,
                                  session_id=None, provider_key=None) -> RuntimeContext:
    llm, rag = _floor(settings, provider_key)
    system_prompt = ""

    if project_id is not None:
        config = await state.get_project_config(project_id)
        if config:
            for col, key in _LLM_MAP.items():
                if config.get(col) is not None:
                    llm[key] = config[col]
            for col, key in _RAG_MAP.items():
                if config.get(col) is not None:
                    rag[key] = config[col]
        # project persona > base_preset > generic
        system_prompt = (config or {}).get("persona_prompt") or ""
        if not system_prompt:
            project = await state.get_project(user_id, project_id)
            if project:
                system_prompt = get_preset(project.get("base_preset", ""))

    return RuntimeContext(
        user_key=user_key, user_id=user_id, project_id=project_id, session_id=session_id,
        llm_settings=llm, rag_settings=rag, system_prompt=system_prompt,
        config_signature=_signature(llm, rag),
    )
