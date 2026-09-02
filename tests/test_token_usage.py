from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from tests.conftest import drain_deferred

from sentient.services.usage import TokenUsage, usage_of

RAW_KEY = "sk-sent-usage-route"


class UsageExtractionTests(unittest.TestCase):
    """LangChain normalises usage onto `usage_metadata` with input/output/total.
    Older providers only populate response_metadata['token_usage']."""

    def test_reads_langchain_usage_metadata(self):
        result = SimpleNamespace(
            usage_metadata={"input_tokens": 812, "output_tokens": 17, "total_tokens": 829},
            response_metadata={},
        )
        self.assertEqual(
            usage_of(result, "gemini-2.5-flash"),
            TokenUsage("gemini-2.5-flash", 812, 17, 829),
        )

    def test_falls_back_to_response_metadata_token_usage(self):
        result = SimpleNamespace(
            usage_metadata=None,
            response_metadata={
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "total_tokens": 120,
                }
            },
        )
        self.assertEqual(usage_of(result, "gpt-4o-mini"), TokenUsage("gpt-4o-mini", 100, 20, 120))

    def test_derives_total_when_the_provider_omits_it(self):
        result = SimpleNamespace(
            usage_metadata={"input_tokens": 10, "output_tokens": 5}, response_metadata={}
        )
        self.assertEqual(usage_of(result, "m").total_tokens, 15)

    def test_a_provider_that_reports_nothing_yields_an_empty_usage(self):
        result = SimpleNamespace(usage_metadata=None, response_metadata={})
        usage = usage_of(result, "mystery-model")
        self.assertEqual(usage.model, "mystery-model")
        self.assertIsNone(usage.total_tokens)

    def test_an_object_with_no_usage_attributes_at_all_does_not_raise(self):
        """A fake LLM in a test, or a provider wrapper that returns a bare object."""
        self.assertEqual(usage_of(object(), "m"), TokenUsage("m", None, None, None))

    def test_a_non_numeric_counter_is_discarded_rather_than_stored(self):
        """A provider that returns null or a string must not poison the column."""
        result = SimpleNamespace(
            usage_metadata={"input_tokens": None, "output_tokens": "many"}, response_metadata={}
        )
        self.assertEqual(usage_of(result, "m"), TokenUsage("m", None, None, None))

    def test_as_kwargs_matches_add_message(self):
        self.assertEqual(
            TokenUsage("m", 1, 2, 3).as_kwargs(),
            {"model": "m", "prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        )


class _UsageChunk:
    """A LangChain chunk that reports usage. Providers attach it to one chunk of
    the stream, and not reliably the last one."""

    def __init__(self, content: str, usage: dict | None = None):
        self.content = content
        self.usage_metadata = usage
        self.response_metadata: dict = {}


class _ScriptedStreamLLM:
    def __init__(self, *chunks: _UsageChunk):
        self._chunks = chunks

    async def astream(self, messages, config=None):
        for chunk in self._chunks:
            yield chunk


class StreamedUsageCaptureTests(unittest.IsolatedAsyncioTestCase):
    async def test_usage_survives_a_trailing_chunk_that_reports_none(self):
        """The reason this does not just read the last chunk: several providers
        emit usage mid-stream and then a final empty chunk carrying the finish
        reason, which would overwrite it with nothing."""
        from sentient.services.chat import stream_completion

        captured: list[tuple[str, TokenUsage]] = []
        llm = _ScriptedStreamLLM(
            _UsageChunk("Greet"),
            _UsageChunk("ings.", {"input_tokens": 40, "output_tokens": 3, "total_tokens": 43}),
            _UsageChunk(""),
        )

        async for _ in stream_completion(
            llm, [], "test-model", on_complete=lambda reply, usage: captured.append((reply, usage))
        ):
            pass

        self.assertEqual(captured, [("Greetings.", TokenUsage("test-model", 40, 3, 43))])

    async def test_a_stream_that_reports_nothing_still_yields_the_model(self):
        from sentient.services.chat import stream_completion

        captured: list[tuple[str, TokenUsage]] = []
        async for _ in stream_completion(
            _ScriptedStreamLLM(_UsageChunk("Hi.")),
            [],
            "test-model",
            on_complete=lambda reply, usage: captured.append((reply, usage)),
        ):
            pass

        self.assertEqual(captured, [("Hi.", TokenUsage("test-model", None, None, None))])

    async def test_a_client_disconnect_yields_an_empty_reply_and_empty_usage(self):
        from sentient.services.chat import stream_completion

        captured: list[tuple[str, TokenUsage]] = []
        async for _ in stream_completion(
            _ScriptedStreamLLM(),
            [],
            "test-model",
            on_complete=lambda reply, usage: captured.append((reply, usage)),
        ):
            pass

        self.assertEqual(captured, [("", TokenUsage("test-model", None, None, None))])


class UsagePersistedByTheGameRouteTests(unittest.IsolatedAsyncioTestCase):
    """The unit tests above pin the extraction. This one proves the number
    actually reaches the assistant row, through the deferred writer."""

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

        user = await deps.state_store.ensure_user("usage-route-owner")
        await deps.state_store.create_api_key(user["id"], hash_key(RAW_KEY))
        self.project = await deps.state_store.create_project(user["id"], "Skyrim")

    async def asyncTearDown(self):
        await drain_deferred()
        self.env.stop()
        self.tmp.cleanup()

    async def _post(self, *, stream: bool):
        class _FakeLLM:
            async def ainvoke(self, messages, config=None):
                return SimpleNamespace(
                    content="Greetings, thane.",
                    usage_metadata={
                        "input_tokens": 812,
                        "output_tokens": 17,
                        "total_tokens": 829,
                    },
                    response_metadata={},
                )

            async def astream(self, messages, config=None):
                yield _UsageChunk("Greetings, ")
                yield _UsageChunk(
                    "thane.",
                    {"input_tokens": 812, "output_tokens": 17, "total_tokens": 829},
                )

        class _StubArchives:
            async def retrieve(self, *args, **kwargs):
                return []

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
                response = await client.post(
                    f"/v1/{RAW_KEY}/{self.project['id']}/chat/completions",
                    json={
                        "messages": [{"role": "user", "content": "Hello."}],
                        "stream": stream,
                    },
                )
                self.assertEqual(response.status_code, 200)
                await drain_deferred()

        threads = await self.deps.state_store.list_threads(self.project["id"])
        self.assertEqual(len(threads), 1)
        return await self.deps.state_store.list_messages(threads[0]["id"])

    async def test_a_non_streamed_turn_records_usage_on_the_assistant_row(self):
        user_row, assistant_row = await self._post(stream=False)
        self.assertIsNone(user_row["total_tokens"])
        self.assertEqual(assistant_row["prompt_tokens"], 812)
        self.assertEqual(assistant_row["completion_tokens"], 17)
        self.assertEqual(assistant_row["total_tokens"], 829)
        self.assertTrue(assistant_row["model"])

    async def test_a_streamed_turn_records_usage_on_the_assistant_row(self):
        _user_row, assistant_row = await self._post(stream=True)
        self.assertEqual(assistant_row["total_tokens"], 829)


if __name__ == "__main__":
    unittest.main()
