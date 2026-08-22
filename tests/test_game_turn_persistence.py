from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from tests.conftest import drain_deferred

from sentient.adapters.llm.openai_wire import OpenAIMessage
from sentient.core.concurrency import SessionLocks
from sentient.services.chat import (
    conversation_prefix_hash,
    conversation_prefix_hash_after,
    record_game_turn,
)
from sentient.services.usage import TokenUsage

RAW_KEY = "sk-sent-game-route"


def _msgs(*pairs: tuple[str, str]) -> list[OpenAIMessage]:
    return [OpenAIMessage(role=role, content=content) for role, content in pairs]


class ConversationPrefixHashTests(unittest.TestCase):
    """The hash is the whole of G4's design: turn N's 'after' hash must equal
    turn N+1's 'before' hash, or every turn opens a new thread."""

    def test_first_turn_has_no_prefix(self):
        messages = _msgs(("system", "You are Lydia."), ("user", "Hello."))
        self.assertIsNone(conversation_prefix_hash(messages))

    def test_the_after_hash_of_turn_n_is_the_before_hash_of_turn_n_plus_1(self):
        turn_one = _msgs(("system", "You are Lydia."), ("user", "Hello."))
        after_one = conversation_prefix_hash_after(turn_one, "Greetings, thane.")

        turn_two = _msgs(
            ("system", "You are Lydia."),
            ("user", "Hello."),
            ("assistant", "Greetings, thane."),
            ("user", "Where are we?"),
        )
        self.assertEqual(conversation_prefix_hash(turn_two), after_one)

    def test_it_holds_across_three_turns(self):
        turn_two = _msgs(
            ("system", "You are Lydia."),
            ("user", "Hello."),
            ("assistant", "Greetings, thane."),
            ("user", "Where are we?"),
        )
        after_two = conversation_prefix_hash_after(turn_two, "Whiterun, my thane.")

        turn_three = _msgs(
            ("system", "You are Lydia."),
            ("user", "Hello."),
            ("assistant", "Greetings, thane."),
            ("user", "Where are we?"),
            ("assistant", "Whiterun, my thane."),
            ("user", "Lead on."),
        )
        self.assertEqual(conversation_prefix_hash(turn_three), after_two)

    def test_the_system_prompt_does_not_affect_the_hash(self):
        """Persona edits between turns must not fork the conversation."""
        first = _msgs(
            ("system", "You are Lydia."),
            ("user", "Hello."),
            ("assistant", "Greetings."),
            ("user", "Again?"),
        )
        second = _msgs(
            ("system", "You are Lydia, housecarl of Whiterun."),
            ("user", "Hello."),
            ("assistant", "Greetings."),
            ("user", "Again?"),
        )
        self.assertEqual(conversation_prefix_hash(first), conversation_prefix_hash(second))

    def test_a_diverged_conversation_hashes_differently(self):
        first = _msgs(("user", "Hello."), ("assistant", "Greetings."), ("user", "Where are we?"))
        second = _msgs(("user", "Hello."), ("assistant", "Well met."), ("user", "Where are we?"))
        self.assertNotEqual(conversation_prefix_hash(first), conversation_prefix_hash(second))

    def test_role_and_content_cannot_be_confused_across_the_boundary(self):
        """A naive join lets 'user'+'ab' and 'usera'+'b' collide."""
        first = _msgs(("user", "ab"), ("user", "x"))
        second = _msgs(("user", "a"), ("user", "b"), ("user", "x"))
        self.assertNotEqual(conversation_prefix_hash(first), conversation_prefix_hash(second))

    def test_none_content_is_treated_as_empty(self):
        messages = [
            OpenAIMessage(role="user", content=None),
            OpenAIMessage(role="assistant", content="hi"),
            OpenAIMessage(role="user", content="next"),
        ]
        self.assertIsNotNone(conversation_prefix_hash(messages))


class GameTurnPersistenceTests(unittest.IsolatedAsyncioTestCase):
    """Replay Mantella-shaped payloads and assert one thread accumulates."""

    async def asyncSetUp(self):
        from sentient.adapters.state.sqlite_store import SQLiteStateStore

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteStateStore(str(Path(self.tmp.name) / "state.db"))
        self.locks = SessionLocks()
        user = await self.store.ensure_user("game-owner")
        self.project = await self.store.create_project(user["id"], "Skyrim")

    def _ctx(self, *, session_id=None, npc_name=None):
        return SimpleNamespace(
            project_id=self.project["id"], session_id=session_id, npc_name=npc_name
        )

    async def _turn(self, messages, reply, **ctx_kwargs):
        await record_game_turn(
            self._ctx(**ctx_kwargs),
            messages,
            reply,
            TokenUsage(),
            state_store=self.store,
            session_locks=self.locks,
        )

    async def test_three_consecutive_turns_land_in_one_thread(self):
        await self._turn(_msgs(("system", "Lydia"), ("user", "Hello.")), "Greetings, thane.")
        await self._turn(
            _msgs(
                ("system", "Lydia"),
                ("user", "Hello."),
                ("assistant", "Greetings, thane."),
                ("user", "Where are we?"),
            ),
            "Whiterun.",
        )
        await self._turn(
            _msgs(
                ("system", "Lydia"),
                ("user", "Hello."),
                ("assistant", "Greetings, thane."),
                ("user", "Where are we?"),
                ("assistant", "Whiterun."),
                ("user", "Lead on."),
            ),
            "At once.",
        )

        threads = await self.store.list_threads(self.project["id"])
        self.assertEqual(len(threads), 1)

        messages = await self.store.list_messages(threads[0]["id"], limit=50)
        self.assertEqual(
            [(m["role"], m["content"]) for m in messages],
            [
                ("user", "Hello."),
                ("assistant", "Greetings, thane."),
                ("user", "Where are we?"),
                ("assistant", "Whiterun."),
                ("user", "Lead on."),
                ("assistant", "At once."),
            ],
        )

    async def test_a_diverged_conversation_opens_a_second_thread(self):
        await self._turn(_msgs(("user", "Hello.")), "Greetings.")
        # Same opening, but the client replays a DIFFERENT assistant line — this is
        # a different conversation and must not be appended to the first.
        await self._turn(
            _msgs(("user", "Hello."), ("assistant", "Well met."), ("user", "Where are we?")),
            "Whiterun.",
        )
        self.assertEqual(len(await self.store.list_threads(self.project["id"])), 2)

    async def test_two_npcs_first_turns_never_collide(self):
        """The empty-prefix rule: an empty prefix must always create."""
        await self._turn(_msgs(("system", "Lydia"), ("user", "Hello.")), "Greetings, thane.")
        await self._turn(_msgs(("system", "Balgruuf"), ("user", "Hello.")), "Speak, then.")
        self.assertEqual(len(await self.store.list_threads(self.project["id"])), 2)

    async def test_a_client_sending_session_id_gets_deterministic_identity(self):
        await self._turn(_msgs(("user", "Hello.")), "Greetings.", session_id="sess-1")
        await self._turn(_msgs(("user", "Again.")), "Indeed.", session_id="sess-1")

        threads = await self.store.list_threads(self.project["id"])
        self.assertEqual(len(threads), 1)
        self.assertEqual(len(await self.store.list_messages(threads[0]["id"], limit=50)), 4)

    async def test_an_empty_reply_is_not_persisted(self):
        """A client disconnect yields "" from stream_completion; that is not a turn."""
        await self._turn(_msgs(("user", "Hello.")), "")
        self.assertEqual(await self.store.list_threads(self.project["id"]), [])

    async def test_a_turn_without_a_project_is_ignored(self):
        ctx = SimpleNamespace(project_id=None, session_id=None, npc_name=None)
        await record_game_turn(
            ctx,
            _msgs(("user", "Hello.")),
            "Greetings.",
            TokenUsage(),
            state_store=self.store,
            session_locks=self.locks,
        )
        self.assertEqual(await self.store.list_threads(self.project["id"]), [])

    async def test_the_thread_is_titled_from_the_npc_when_one_is_known(self):
        await self._turn(_msgs(("user", "Hello.")), "Greetings.", npc_name="Lydia")
        threads = await self.store.list_threads(self.project["id"])
        self.assertEqual(threads[0]["npc_name"], "Lydia")
        self.assertEqual(threads[0]["title"], "Lydia")


class GameTurnRouteTests(unittest.IsolatedAsyncioTestCase):
    """The unit tests above call record_game_turn directly. This one drives the
    real route twice, which is the only thing that proves the payload Mantella
    actually sends produces a matching prefix on the following turn."""

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"DATA_DIR": self.tmp.name}, clear=False)
        self.env.start()
        for name in ("DATABASE_URL", "NEON_AUTH_JWKS_URL"):
            os.environ.pop(name, None)

        from sentient.adapters.auth import IdentityCache, hash_key
        from sentient.adapters.state import get_state_store
        from sentient.api import app as api
        from sentient.api import deps
        from sentient.core.cache import ObjectRegistry
        from sentient.core.config import load_rag_settings
        from sentient.services.runtime import RuntimeCache

        self.api = api
        self.deps = deps
        deps._settings = load_rag_settings()
        deps.state_store = get_state_store(deps._settings)
        deps.identity_cache = IdentityCache()
        deps.runtime_cache = RuntimeCache()
        deps.object_registry = ObjectRegistry()
        deps.get_default_archives.cache_clear()

        user = await deps.state_store.ensure_user("game-route-owner")
        await deps.state_store.create_api_key(user["id"], hash_key(RAW_KEY))
        self.project = await deps.state_store.create_project(user["id"], "Skyrim")

    async def asyncTearDown(self):
        await drain_deferred()
        self.env.stop()
        self.tmp.cleanup()

    async def test_two_route_turns_accumulate_in_one_thread(self):
        replies = iter(["Greetings, thane.", "Whiterun."])

        class _FakeLLM:
            async def ainvoke(self, messages):
                return SimpleNamespace(content=next(replies))

        class _StubArchives:
            async def retrieve(self, *args, **kwargs):
                return []

        first = [
            {"role": "system", "content": "Lydia"},
            {"role": "user", "content": "Hello."},
        ]
        # Exactly what Mantella resends: the whole conversation, including the
        # reply it just received, plus the new player line.
        second = first + [
            {"role": "assistant", "content": "Greetings, thane."},
            {"role": "user", "content": "Where are we?"},
        ]

        with (
            patch.object(self.deps, "build_llm", new_callable=AsyncMock, return_value=_FakeLLM()),
            patch.object(
                self.deps,
                "get_archives_for_context",
                new_callable=AsyncMock,
                return_value=_StubArchives(),
                create=True,
            ),
        ):
            transport = httpx.ASGITransport(app=self.api.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                for payload in (first, second):
                    response = await client.post(
                        f"/v1/{RAW_KEY}/{self.project['id']}/chat/completions",
                        json={"messages": payload, "stream": False},
                    )
                    self.assertEqual(response.status_code, 200)
                    # Fire-and-forget, and the next turn's prefix depends on it.
                    await drain_deferred()

        threads = await self.deps.state_store.list_threads(self.project["id"])
        self.assertEqual(len(threads), 1)
        messages = await self.deps.state_store.list_messages(threads[0]["id"])
        self.assertEqual(
            [(m["role"], m["content"]) for m in messages],
            [
                ("user", "Hello."),
                ("assistant", "Greetings, thane."),
                ("user", "Where are we?"),
                ("assistant", "Whiterun."),
            ],
        )


if __name__ == "__main__":
    unittest.main()
