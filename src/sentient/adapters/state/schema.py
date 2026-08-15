"""Column and sentinel constants shared by both StateStore implementations.

SQLiteStateStore and PostgresStateStore are peers behind one Protocol. These
constants live here so neither has to import the other's privates -- the leak
the R9 design calls out in section 7.3.
"""

from __future__ import annotations

# Whitelisted project_config columns — guards the **fields upsert against SQL injection
# and typos (only these keys are ever written).
_CONFIG_COLUMNS = (
    "llm_provider",
    "embedding_provider",
    "model_name",
    "embedding_model_name",
    "temperature",
    "max_tokens",
    "mrl_vector_size",
    "reasoning_effort",
    "reasoning_format",
    "rag_search_type",
    "rag_top_k",
    "rag_fetch_k",
    "rag_mmr_lambda",
    "rag_score_threshold",
    "rag_chunk_size",
    "rag_chunk_overlap",
    "persona_prompt",
    "history_window",
    "embedding_signature",
)

_DEFAULT_USER_SENTINEL = "__default__"
