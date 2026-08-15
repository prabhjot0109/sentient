from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from sentient.adapters.llm.openai_wire import ChatCompletionRequest
from sentient.api.routers import completions as completions_router
from sentient.services import chat as chat_service


class RuntimeCompletionsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ,
            {"DATA_DIR": self.tmp.name},
            clear=False,
        )
        self.env.start()
        for name in ("DATABASE_URL", "NEON_AUTH_JWKS_URL"):
            os.environ.pop(name, None)

        from sentient.adapters.auth import IdentityCache
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

    async def asyncTearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()

    async def test_env_default_route_uses_runtime_llm_builder(self) -> None:
        class _FakeLLM:
            async def ainvoke(self, messages):
                class _Response:
                    content = "Greetings, traveler."

                return _Response()

        class _StubArchives:
            async def retrieve(self, *args, **kwargs):
                return []

        with (
            patch.object(
                self.deps,
                "build_llm",
                new_callable=AsyncMock,
                return_value=_FakeLLM(),
            ) as build_llm,
            patch.object(
                self.deps,
                "get_archives_for_context",
                new_callable=AsyncMock,
                return_value=_StubArchives(),
                create=True,
            ) as get_archives_for_context,
            patch.object(self.deps, "get_archives", return_value=_StubArchives()),
        ):
            transport = httpx.ASGITransport(app=self.api.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/v1/chat/completions",
                    json={
                        "messages": [{"role": "user", "content": "hi"}],
                        "stream": False,
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["choices"][0]["message"]["content"],
            "Greetings, traveler.",
        )
        build_llm.assert_awaited_once()
        get_archives_for_context.assert_awaited_once()

    async def test_project_route_resolves_persona_and_filters_retrieval(self) -> None:
        from sentient.adapters.auth import hash_key, user_key_of

        user = await self.deps.state_store.ensure_user("owner")
        await self.deps.state_store.create_api_key(user["id"], hash_key("sk-sent-project"))
        project = await self.deps.state_store.create_project(
            user["id"], "Skyrim", base_preset="skyrim"
        )
        captured: dict[str, object] = {}

        class _FakeLLM:
            async def ainvoke(self, messages):
                captured["system"] = messages[0].content

                class _Response:
                    content = "By the Nine!"

                return _Response()

        class _StubArchives:
            async def retrieve(self, *args, **kwargs):
                captured["retrieve_kwargs"] = kwargs
                return []

        with (
            patch.object(
                self.deps,
                "build_llm",
                new_callable=AsyncMock,
                return_value=_FakeLLM(),
            ),
            patch.object(
                self.deps,
                "get_archives_for_context",
                new_callable=AsyncMock,
                return_value=_StubArchives(),
                create=True,
            ) as get_archives_for_context,
        ):
            transport = httpx.ASGITransport(app=self.api.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/v1/sk-sent-project/{project['id']}/chat/completions",
                    json={
                        "messages": [
                            {"role": "system", "content": "Caller persona."},
                            {"role": "user", "content": "hail"},
                        ],
                        "stream": False,
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Skyrim", str(captured["system"]))
        self.assertIn("Caller persona.", str(captured["system"]))
        self.assertEqual(
            captured["retrieve_kwargs"]["project_id"],  # type: ignore[index]
            project["id"],
        )
        self.assertEqual(
            captured["retrieve_kwargs"]["user_key"],  # type: ignore[index]
            user_key_of("sk-sent-project"),
        )
        get_archives_for_context.assert_awaited_once()

    async def test_api_key_only_route_uses_resolved_identity(self) -> None:
        from sentient.adapters.auth import hash_key, user_key_of

        user = await self.deps.state_store.ensure_user("key-owner")
        await self.deps.state_store.create_api_key(user["id"], hash_key("sk-sent-key-only"))
        captured: dict[str, object] = {}

        class _FakeLLM:
            async def ainvoke(self, messages):
                class _Response:
                    content = "Ready."

                return _Response()

        class _StubArchives:
            async def retrieve(self, *args, **kwargs):
                captured.update(kwargs)
                return []

        with (
            patch.object(
                self.deps,
                "build_llm",
                new_callable=AsyncMock,
                return_value=_FakeLLM(),
            ),
            patch.object(
                self.deps,
                "get_archives_for_context",
                new_callable=AsyncMock,
                return_value=_StubArchives(),
            ),
        ):
            transport = httpx.ASGITransport(app=self.api.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/v1/sk-sent-key-only/chat/completions",
                    json={"messages": [{"role": "user", "content": "hi"}]},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["user_key"], user_key_of("sk-sent-key-only"))
        self.assertIsNone(captured["project_id"])

    async def test_streaming_route_keeps_openai_sse_contract(self) -> None:
        class _FakeLLM:
            async def astream(self, messages):
                class _Chunk:
                    content = "Greetings."

                yield _Chunk()

            def stream(self, messages):
                raise AssertionError("sync streaming must not run on the event loop")

        class _StubArchives:
            async def retrieve(self, *args, **kwargs):
                return []

        with (
            patch.object(
                self.deps,
                "build_llm",
                new_callable=AsyncMock,
                return_value=_FakeLLM(),
            ),
            patch.object(
                self.deps,
                "get_archives_for_context",
                new_callable=AsyncMock,
                return_value=_StubArchives(),
            ),
        ):
            transport = httpx.ASGITransport(app=self.api.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/v1/chat/completions",
                    json={
                        "messages": [{"role": "user", "content": "hi"}],
                        "stream": True,
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/event-stream; charset=utf-8")
        self.assertIn('"content": "Greetings."', response.text)
        self.assertTrue(response.text.endswith("data: [DONE]\n\n"))

    async def test_llm_resolution_and_retrieval_start_concurrently(self) -> None:
        llm_started = asyncio.Event()
        retrieval_started = asyncio.Event()

        class _FakeLLM:
            async def ainvoke(self, messages):
                class _Response:
                    content = "Ready."

                return _Response()

        class _StubArchives:
            async def retrieve(self, *args, **kwargs):
                retrieval_started.set()
                await asyncio.wait_for(llm_started.wait(), timeout=0.2)
                return []

        async def get_llm(ctx):
            llm_started.set()
            await asyncio.wait_for(retrieval_started.wait(), timeout=0.2)
            return _FakeLLM()

        with (
            patch.object(self.deps, "get_llm", side_effect=get_llm),
            patch.object(
                self.deps,
                "get_archives_for_context",
                new_callable=AsyncMock,
                return_value=_StubArchives(),
            ),
        ):
            ctx = await self.deps.completions_ctx(None, None)
            request = ChatCompletionRequest(messages=[{"role": "user", "content": "hi"}])
            response = await asyncio.wait_for(
                completions_router._run_completions(request, ctx), timeout=0.3
            )

        self.assertEqual(response["choices"][0]["message"]["content"], "Ready.")

    async def test_faiss_archives_are_cached_per_user_and_project_scope(self) -> None:
        owner = await self.deps.state_store.ensure_user("archive-owner")
        first_project = await self.deps.state_store.create_project(owner["id"], "First")
        second_project = await self.deps.state_store.create_project(owner["id"], "Second")
        first_ctx = await self.deps.runtime_cache.resolve(
            self.deps.state_store,
            self.deps._settings,
            user_id=owner["id"],
            user_key="tenant-key",
            project_id=first_project["id"],
        )
        second_ctx = await self.deps.runtime_cache.resolve(
            self.deps.state_store,
            self.deps._settings,
            user_id=owner["id"],
            user_key="tenant-key",
            project_id=second_project["id"],
        )
        self.assertEqual(first_ctx.config_signature, second_ctx.config_signature)

        first_archives = object()
        second_archives = object()
        with patch.object(
            self.deps,
            "build_archives",
            new_callable=AsyncMock,
            side_effect=[first_archives, second_archives],
        ) as build_archives:
            first = await self.deps.get_archives_for_context(first_ctx)
            first_again = await self.deps.get_archives_for_context(first_ctx)
            second = await self.deps.get_archives_for_context(second_ctx)

        self.assertIs(first, first_again)
        self.assertIsNot(first, second)
        self.assertEqual(build_archives.await_count, 2)

    async def test_unknown_key_on_project_route_is_401(self) -> None:
        transport = httpx.ASGITransport(app=self.api.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/sk-sent-missing/project/chat/completions",
                json={"messages": [{"role": "user", "content": "x"}]},
            )

        self.assertEqual(response.status_code, 401)

    async def test_project_owned_by_another_user_is_403(self) -> None:
        from sentient.adapters.auth import hash_key

        owner = await self.deps.state_store.ensure_user("project-owner")
        other = await self.deps.state_store.ensure_user("other-user")
        project = await self.deps.state_store.create_project(owner["id"], "Private")
        await self.deps.state_store.create_api_key(other["id"], hash_key("sk-sent-other"))

        transport = httpx.ASGITransport(app=self.api.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/v1/sk-sent-other/{project['id']}/chat/completions",
                json={"messages": [{"role": "user", "content": "x"}]},
            )

        self.assertEqual(response.status_code, 403)

    async def test_runtime_route_preserves_query_condensation(self) -> None:
        from dataclasses import replace

        self.deps._settings = replace(self.deps._settings, condense_queries=True)
        captured: dict[str, object] = {}

        class _FakeLLM:
            async def ainvoke(self, messages):
                class _Response:
                    content = "Nords are hardy."

                return _Response()

        class _StubArchives:
            async def retrieve(self, query, **kwargs):
                captured["query"] = query
                return []

        with (
            patch.object(
                self.deps,
                "build_llm",
                new_callable=AsyncMock,
                return_value=_FakeLLM(),
            ),
            patch.object(
                self.deps,
                "get_archives_for_context",
                new_callable=AsyncMock,
                return_value=_StubArchives(),
            ),
            patch.object(
                chat_service,
                "condense_query",
                new_callable=AsyncMock,
                return_value="What skills do Nords have?",
            ) as condense,
        ):
            transport = httpx.ASGITransport(app=self.api.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/v1/chat/completions",
                    json={
                        "messages": [
                            {"role": "user", "content": "Tell me about Nords."},
                            {"role": "assistant", "content": "They are hardy."},
                            {"role": "user", "content": "What skills do they have?"},
                        ]
                    },
                )

        self.assertEqual(response.status_code, 200)
        condense.assert_awaited_once()
        self.assertEqual(captured["query"], "What skills do Nords have?")


if __name__ == "__main__":
    unittest.main()
