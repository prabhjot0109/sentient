"""Column and sentinel constants shared by both StateStore implementations.

SQLiteStateStore and PostgresStateStore are peers behind one Protocol. These
constants live here so neither has to import the other's privates -- the leak
the R9 design calls out in section 7.3.
"""

from __future__ import annotations

import json
from typing import Any

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


def _decode_sources(row: dict[str, Any]) -> dict[str, Any]:
    """Turn a message row's stored `sources` back into a list.

    Both stores keep the column as JSON TEXT/jsonb and asyncpg hands jsonb back
    as a string, so neither returns a list on its own. Decoding in one shared
    place is what stops the two stores disagreeing about the type of a field the
    console renders -- the divergence class that has already cost four plan
    revisions on this codebase.

    NULL stays None, which means "not recorded": every row written before the
    column existed, and every surface that does not retrieve. `[]` is different
    and real -- retrieval ran and matched nothing. Unparseable text degrades to
    None rather than raising, because a transcript is worth more than a column.
    """
    raw = row.get("sources")
    if isinstance(raw, str):
        try:
            row["sources"] = json.loads(raw)
        except (ValueError, TypeError):
            row["sources"] = None
    return row
