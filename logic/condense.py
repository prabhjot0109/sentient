from __future__ import annotations

import re

# Ambiguous referents that break vector retrieval when embedded literally. Word-
# boundary matched so "item"/"pheasant" don't trigger on "it"/"he" substrings.
_AMBIGUOUS = (
    "they", "them", "their", "theirs", "those", "these",
    "it", "its", "he", "she", "him", "her", "his",
)
_PRONOUN_RE = re.compile(r"\b(" + "|".join(_AMBIGUOUS) + r")\b", re.IGNORECASE)


def needs_condensation(text: str) -> bool:
    """True when the query contains an ambiguous pronoun and likely needs history
    to resolve. Cheap regex — the TTFT gate before any LLM rewrite call."""
    return bool(text) and _PRONOUN_RE.search(text) is not None
