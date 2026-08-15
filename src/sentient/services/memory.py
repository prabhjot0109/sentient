from __future__ import annotations

from collections import defaultdict, deque

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


class SessionMemory:
    """In-process rolling conversation window keyed by (session_id, npc_name).

    Web-path only: the Mantella game path resends full history each turn, so it
    does NOT use this. Not persisted — long-term state is Supabase (Plan 05).
    Bounded by max_turns so parallel sessions can't leak RAM unboundedly.
    """

    def __init__(self, max_turns: int = 12) -> None:
        self._max = max_turns
        self._threads: dict[tuple[str, str], deque[BaseMessage]] = defaultdict(
            lambda: deque(maxlen=self._max)
        )

    def append(self, session_id: str, npc_name: str, role: str, content: str) -> None:
        msg = AIMessage(content=content) if role == "assistant" else HumanMessage(content=content)
        self._threads[(session_id, npc_name)].append(msg)

    def history(self, session_id: str, npc_name: str) -> list[BaseMessage]:
        return list(self._threads.get((session_id, npc_name), ()))

    def clear(self, session_id: str, npc_name: str | None = None) -> None:
        if npc_name is not None:
            self._threads.pop((session_id, npc_name), None)
            return
        for key in [k for k in self._threads if k[0] == session_id]:
            self._threads.pop(key, None)
