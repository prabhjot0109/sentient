from __future__ import annotations

import asyncio
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from cryptography.fernet import Fernet
from tests.conftest import drain_deferred

from sentient.adapters.auth import IdentityCache
from sentient.adapters.state.sqlite_store import SQLiteStateStore
from sentient.core.cache import ObjectRegistry
from sentient.services.runtime import RuntimeCache


class ThreadStoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SQLiteStateStore(str(Path(self.tmp.name) / "state.db"))

    def tearDown(self):
        self.tmp.cleanup()

    async def _project(self):
        user = await self.store.ensure_user("A")
        return user, await self.store.create_project(user["id"], "P")

    async def test_thread_upsert_and_message_tail_are_stable_and_chronological(self):
        _, project = await self._project()
        first = await self.store.upsert_thread(project["id"], "session", title="First")
        second = await self.store.upsert_thread(project["id"], "session")
        self.assertEqual(first["id"], second["id"])
        for index in range(30):
            await self.store.add_message(
                first["id"], "user" if index % 2 == 0 else "assistant", f"m{index}"
            )
        tail = await self.store.list_messages(first["id"], limit=20)
        self.assertEqual([row["content"] for row in tail], [f"m{i}" for i in range(10, 30)])

    async def test_message_order_survives_identical_timestamps(self):
        """A coarse clock must not let the assistant reply sort before its question."""
        _, project = await self._project()
        thread = await self.store.upsert_thread(project["id"], "session")
        with patch(
            "sentient.adapters.state.sqlite_store._now", return_value="2026-07-10T00:00:00+00:00"
        ):
            for index in range(6):
                await self.store.add_message(thread["id"], "user", f"m{index}")
        tail = await self.store.list_messages(thread["id"], limit=4)
        self.assertEqual([row["content"] for row in tail], ["m2", "m3", "m4", "m5"])


class ThreadMemoryEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from sentient.api import app as api
        from sentient.api import deps

        self.api = api
        self.deps = deps
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SQLiteStateStore(str(Path(self.tmp.name) / "state.db"))
        self.original = (
            deps.state_store,
            deps._settings,
            deps.runtime_cache,
            deps.object_registry,
            deps.identity_cache,
        )
        deps.state_store = self.store
        # /v1/chat refuses to run with no credential anywhere; the vault secret keeps
        # the test independent of whichever provider keys the dev machine has set.
        deps._settings = replace(deps._settings, sentient_secret_key=Fernet.generate_key().decode())
        deps.runtime_cache = RuntimeCache()
        deps.object_registry = ObjectRegistry()
        deps.identity_cache = IdentityCache()
        self.owner = await self.store.ensure_user(None)
        self.project = await self.store.create_project(self.owner["id"], "P")
        await self.store.upsert_project_config(self.project["id"], llm_provider="openai")
        self.captured: list[list[str]] = []
        transport = httpx.ASGITransport(app=api.app)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        await self._drain_deferred()
        (
            self.deps.state_store,
            self.deps._settings,
            self.deps.runtime_cache,
            self.deps.object_registry,
            self.deps.identity_cache,
        ) = self.original
        self.api.app.dependency_overrides.clear()
        self.tmp.cleanup()

    @staticmethod
    async def _drain_deferred():
        """Let post-response writes finish before the temp DB is removed — Windows
        refuses to unlink a file another thread still has open."""
        pending = [
            task
            for task in asyncio.all_tasks()
            if (task.get_name() or "").startswith("sentient-deferred-")
        ]
        if pending:
            await asyncio.wait(pending, timeout=2)

    def _fake_generation(self):
        """Patch the LLM and retrieval seams, recording every prompt the LLM sees."""
        captured = self.captured

        class FakeLLM:
            async def ainvoke(self, messages):
                captured.append([str(message.content) for message in messages])
                return SimpleNamespace(content="reply")

            async def astream(self, messages):
                captured.append([str(message.content) for message in messages])
                yield SimpleNamespace(content="reply")

        class EmptyArchives:
            async def retrieve(self, *args, **kwargs):
                return []

        return (
            patch.object(self.deps, "get_llm", AsyncMock(return_value=FakeLLM())),
            patch.object(self.deps, "build_llm", AsyncMock(return_value=FakeLLM())),
            patch.object(
                self.deps, "get_archives_for_context", AsyncMock(return_value=EmptyArchives())
            ),
        )

    async def _say(self, message, **body):
        return await self.client.post("/v1/chat", json={"message": message, **body})

    async def test_second_turn_receives_persisted_history_and_sidebar_is_owned(self):
        llm, _, archives = self._fake_generation()
        with llm, archives:
            first = await self._say("first turn", project_id=self.project["id"])
            self.assertEqual(first.status_code, 200)
            thread_id = first.json()["thread_id"]
            await asyncio.sleep(0.05)  # let the deferred turn write land
            second = await self._say(
                "second turn", project_id=self.project["id"], thread_id=thread_id
            )
            self.assertEqual(second.status_code, 200)
            self.assertIn("first turn", self.captured[-1])
            self.assertIn("reply", self.captured[-1])

            sidebar = await self.client.get(f"/v1/projects/{self.project['id']}/threads")
            self.assertEqual(sidebar.status_code, 200)
            self.assertEqual(sidebar.json()["threads"][0]["title"], "first turn")

            history = await self.client.get(f"/v1/threads/{thread_id}/messages")
            self.assertEqual(
                [(row["role"], row["content"]) for row in history.json()["messages"]][:2],
                [("user", "first turn"), ("assistant", "reply")],
            )

            self._become_another_user()
            self.assertEqual(
                (await self.client.get(f"/v1/threads/{thread_id}/messages")).status_code, 404
            )
            self.assertEqual(
                (await self.client.get(f"/v1/projects/{self.project['id']}/threads")).status_code,
                404,
            )

    async def test_history_folded_into_generation_is_capped_by_history_window(self):
        await self.store.upsert_project_config(self.project["id"], history_window=2)
        thread = await self.store.upsert_thread(self.project["id"], "sess", title="T")
        for index in range(6):
            await self.store.add_message(thread["id"], "user", f"old-{index}")

        llm, _, archives = self._fake_generation()
        with llm, archives:
            answered = await self._say("now", project_id=self.project["id"], thread_id=thread["id"])
        self.assertEqual(answered.status_code, 200)
        prompt = self.captured[-1]
        self.assertIn("old-5", prompt)
        self.assertIn("old-4", prompt)
        self.assertNotIn("old-3", prompt)  # window=2 keeps exactly the last two

    async def test_thread_id_without_project_id_is_rejected(self):
        rejected = await self._say("orphan", thread_id="whatever")
        self.assertEqual(rejected.status_code, 400)

    async def test_foreign_thread_and_project_are_not_reachable(self):
        llm, _, archives = self._fake_generation()
        with llm, archives:
            started = await self._say("mine", project_id=self.project["id"])
        thread_id = started.json()["thread_id"]

        self._become_another_user()
        llm, _, archives = self._fake_generation()
        with llm, archives:
            foreign = await self._say("yours", project_id=self.project["id"], thread_id=thread_id)
        self.assertEqual(foreign.status_code, 404)

    async def test_chat_without_a_project_keeps_the_legacy_shape(self):
        """No project_id => no thread, no memory, no deferral — as before R7."""
        brain = SimpleNamespace(
            ask_with_context=AsyncMock(return_value={"answer": "legacy", "sources": [], "top_k": 3})
        )
        with patch.object(self.deps, "get_brain", AsyncMock(return_value=brain)):
            answered = await self._say("plain")
        self.assertEqual(answered.status_code, 200)
        self.assertEqual(answered.json()["response"], "legacy")
        self.assertIsNone(answered.json()["thread_id"])
        self.assertEqual(await self.store.list_threads(self.project["id"]), [])

    async def test_game_route_persists_the_turn_without_reading_memory(self):
        from sentient.adapters.auth import hash_key

        await self.store.create_api_key(self.owner["id"], hash_key("sk-sent-game"))
        _, build_llm, archives = self._fake_generation()
        with build_llm, archives:
            answered = await self.client.post(
                f"/v1/sk-sent-game/{self.project['id']}/chat/completions",
                json={
                    "messages": [{"role": "user", "content": "hail"}],
                    "session_id": "mantella-session-1",
                    "npc_name": "Lydia",
                    "stream": False,
                },
            )
        self.assertEqual(answered.status_code, 200)
        await drain_deferred()  # the transcript write is deferred past the reply

        threads = await self.store.list_threads(self.project["id"])
        self.assertEqual(
            [(t["session_id"], t["npc_name"]) for t in threads], [("mantella-session-1", "Lydia")]
        )
        # G4 persists both sides so the console can replay the conversation. The
        # game path still never *reads* it back: Mantella carries the history in
        # its own payload, and injecting a second copy would duplicate context.
        self.assertEqual(
            [(m["role"], m["content"]) for m in await self.store.list_messages(threads[0]["id"])],
            [("user", "hail"), ("assistant", "reply")],
        )

    def _become_another_user(self):
        async def other_user():
            other = await self.store.ensure_user("other")
            return other["id"], "other"

        self.api.app.dependency_overrides[self.deps.current_user] = other_user


if __name__ == "__main__":
    unittest.main()
