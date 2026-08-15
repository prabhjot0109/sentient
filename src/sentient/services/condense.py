from __future__ import annotations

import re

from langchain_core.messages import BaseMessage

# Ambiguous referents that break vector retrieval when embedded literally. Word-
# boundary matched so "item"/"pheasant" don't trigger on "it"/"he" substrings.
_AMBIGUOUS = (
    "they",
    "them",
    "their",
    "theirs",
    "those",
    "these",
    "it",
    "its",
    "he",
    "she",
    "him",
    "her",
    "his",
)
_PRONOUN_RE = re.compile(r"\b(" + "|".join(_AMBIGUOUS) + r")\b", re.IGNORECASE)


def needs_condensation(text: str) -> bool:
    """True when the query contains an ambiguous pronoun and likely needs history
    to resolve. Cheap regex — the TTFT gate before any LLM rewrite call."""
    return bool(text) and _PRONOUN_RE.search(text) is not None


_MAX_HISTORY_TURNS = 6
_CONDENSE_SYSTEM = (
    "You rewrite a follow-up question into a single standalone search query. "
    "Resolve pronouns using the chat history. Output ONLY the rewritten query — "
    "no quotes, no preamble, no explanation. If it is already standalone, echo it."
)


def _format_history(history: list[BaseMessage]) -> str:
    lines = []
    for m in history[-_MAX_HISTORY_TURNS:]:
        role = "User" if m.__class__.__name__ == "HumanMessage" else "NPC"
        lines.append(f"{role}: {str(m.content).strip()}")
    return "\n".join(lines)


async def condense_query(llm, history: list[BaseMessage], question: str) -> str:
    """Rewrite `question` into a standalone retrieval query — only when the gate
    fires. Never raises: on any failure returns the original question so retrieval
    still runs. The result is for RETRIEVAL ONLY; generation keeps raw history."""
    if not needs_condensation(question):
        return question
    from langchain_core.messages import HumanMessage, SystemMessage

    prompt = [
        SystemMessage(content=_CONDENSE_SYSTEM),
        HumanMessage(
            content=f"Chat history:\n{_format_history(history)}\n\n"
            f"Follow-up: {question}\n\nStandalone query:"
        ),
    ]
    try:
        result = await llm.ainvoke(prompt)
        text = str(getattr(result, "content", "")).strip()
        return text.splitlines()[0].strip() if text else question
    except Exception:
        return question
