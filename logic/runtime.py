from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, replace
from typing import Any

from cachetools import TTLCache

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
    status: str = "active"


def embedding_signature(rag_settings: dict[str, Any]) -> str:
    """Return a stable identifier for the embedding space used by a project."""
    provider = rag_settings.get("embedding_provider")
    model = rag_settings.get("embedding_model")
    dimension = rag_settings.get("mrl_vector_size") or "default"
    payload = f"{provider}|{model}|{dimension}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


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
    project = None

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
        project = await state.get_project(user_id, project_id)
        if not system_prompt:
            if project:
                system_prompt = get_preset(project.get("base_preset", ""))

    return RuntimeContext(
        user_key=user_key, user_id=user_id, project_id=project_id, session_id=session_id,
        llm_settings=llm, rag_settings=rag, system_prompt=system_prompt,
        config_signature=_signature(llm, rag),
        status=(project or {}).get("status", "active"),
    )


class RuntimeCache:
    """Memoizes contexts by identity, project, and provider credential. Short TTL as a
    backstop; call invalidate(project_id) on config/persona writes for immediate
    freshness. Keeps project-config DB reads off the per-turn hot path.

    Single-flight is per identity/project/credential — a cold resolve for one
    project never blocks another's. Locks are keyed by (event loop, memo key) because
    asyncio.Lock binds to the loop it was created on; entries drop once settled.
    """

    def __init__(self, ttl: float = 60, maxsize: int = 512) -> None:
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._locks: dict[tuple, asyncio.Lock] = {}

    async def resolve(self, state, settings, *, user_id, user_key, project_id,
                      session_id=None, provider_key=None) -> RuntimeContext:
        provider_fingerprint = hashlib.sha256(
            (provider_key or "").encode()
        ).hexdigest()[:16]
        cache_key = (user_id, user_key, project_id, provider_fingerprint)
        hit = self._cache.get(cache_key)
        if hit is None:
            lock_key = (id(asyncio.get_running_loop()), *cache_key)
            lock = self._locks.setdefault(lock_key, asyncio.Lock())
            try:
                async with lock:
                    hit = self._cache.get(cache_key)
                    if hit is None:
                        hit = await resolve_runtime_context(
                            state, settings, user_id=user_id, user_key=user_key,
                            project_id=project_id, session_id=session_id,
                            provider_key=provider_key)
                        self._cache[cache_key] = hit
            finally:
                self._locks.pop(lock_key, None)
        # session_id varies per call but isn't part of config; return a context carrying this call's id
        if hit.session_id != session_id:
            return replace(hit, session_id=session_id)
        return hit

    def invalidate(self, project_id: str) -> None:
        for key in [k for k in self._cache if k[2] == project_id]:
            self._cache.pop(key, None)
