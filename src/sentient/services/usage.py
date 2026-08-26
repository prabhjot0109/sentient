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
from datetime import UTC, datetime, timedelta
from typing import Any

from sentient.core.errors import QuotaExceeded


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


# --- The quota, which is a read of everything above ---------------------------
#
# It lives here rather than in services/chat.py because it is not a step in
# generating a turn -- it is a question about accumulated usage, and this module
# already owns the answer to "how many tokens did that cost". chat.py calls it;
# nothing else needs to know how the window is computed.

QUOTA_WINDOW = timedelta(days=30)


async def assert_within_quota(state_store, settings, *, user_id: str | None) -> None:
    """Raise `QuotaExceeded` if this user has spent their allowance.

    Called BEFORE the provider, and that ordering is the whole point: the request
    that trips the quota must not also be the request that spends the money.

    A rolling 30 days, not a calendar month. The env var is named
    TOKEN_QUOTA_PER_MONTH because that is what an operator thinks in, but a
    calendar boundary would need a timezone nobody has chosen and would let a
    caller spend two months' budget across midnight on the 31st.

    Two deliberate holes, stated rather than discovered later:

    - It counts only turns Sentient itself recorded. Embedding calls during
      ingestion, and any provider spend outside `chat_messages`, are invisible
      here. H6's disk quota is what bounds ingestion.
    - `total_tokens` is nullable: a provider that reports no usage contributes
      zero. The sum under-counts rather than guessing, which is the same choice
      `usage_of` makes one layer down.
    """
    limit = getattr(settings, "token_quota_per_month", 0)
    if limit <= 0 or user_id is None:
        return

    spent = await state_store.sum_user_tokens(user_id, datetime.now(UTC) - QUOTA_WINDOW)
    if spent >= limit:
        raise QuotaExceeded(
            f"monthly token quota reached ({spent} of {limit}); it resets as usage ages out"
        )
