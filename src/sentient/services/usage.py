"""Token accounting, read in one place.

Providers disagree on where usage lands. LangChain normalises most of them onto
`usage_metadata` (`input_tokens` / `output_tokens` / `total_tokens`); some only
populate `response_metadata["token_usage"]` with OpenAI's older field names.
This module owns that disagreement so nothing else has to know about it.

Reading these attributes is free — they are already on the response object. The
*write* belongs in the deferred path; see `services/chat.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TokenUsage:
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    def as_kwargs(self) -> dict[str, Any]:
        """Exactly the keyword arguments `StateStore.add_message` accepts."""
        return {
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


def _as_int(value: Any) -> int | None:
    """None for anything that is not already a number. A provider that returns
    null or a string must leave the column null rather than store a guess."""
    return int(value) if isinstance(value, int | float) else None


def _counts(source: Any, prompt_key: str, completion_key: str) -> tuple[int | None, ...]:
    if not isinstance(source, dict):
        return (None, None, None)
    return (
        _as_int(source.get(prompt_key)),
        _as_int(source.get(completion_key)),
        _as_int(source.get("total_tokens")),
    )


def usage_of(result: Any, model: str | None = None) -> TokenUsage:
    """Best-effort usage for one completion.

    Never raises: a missing counter is a gap in a dashboard, not a reason to fail
    a player's turn. The two sources are never mixed — a total from one provider
    shape and a prompt count from the other would be a number nobody could
    reconcile later.
    """
    prompt, completion, total = _counts(
        getattr(result, "usage_metadata", None), "input_tokens", "output_tokens"
    )

    if prompt is None and completion is None and total is None:
        legacy = getattr(result, "response_metadata", None)
        prompt, completion, total = _counts(
            legacy.get("token_usage") if isinstance(legacy, dict) else None,
            "prompt_tokens",
            "completion_tokens",
        )

    if total is None and (prompt is not None or completion is not None):
        total = (prompt or 0) + (completion or 0)

    return TokenUsage(model, prompt, completion, total)
