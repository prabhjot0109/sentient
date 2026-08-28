"""B1: `POST /v1/chat` renders SSE when asked, and exactly today's JSON when not.

The game route has streamed since R5. This route could not, which is why F8 sat
in the backlog. R9 removed the structural reason — both surfaces are renderers
over one grounded turn — so this is a rendering change, not a re-implementation.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from langchain_core.embeddings import Embeddings
from tests.conftest import drain_deferred


class FakeEmbeddings(Embeddings):
    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 1.0, 0.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


class _FakeLLM:
    """Serves both renderers, so one fixture proves they agree on the reply.

    A separate streaming double would let the two paths drift and still pass.
    """

    def __init__(self, reply: str):
        self._reply = reply

    async def ainvoke(self, messages):
        class _Response:
            content = self._reply

        return _Response()

    async def astream(self, messages):
        for piece in self._reply.split(" "):

            class _Chunk:
                content = piece + " "

            yield _Chunk()


class _StubArchives:
    def __init__(self, chunks=None):
        self._chunks = chunks or []

    async def retrieve(self, *args, **kwargs):
        return self._chunks


class WebChatStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ,
            {
                "DATA_DIR": self.tmp.name,
                "VECTOR_BACKEND": "faiss",
                # The route refuses before it reaches the LLM unless some provider
                # credential exists; the LLM itself is patched out below.
                "GOOGLE_API_KEY": "test-key",
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)

        embeddings = patch(
            "sentient.adapters.documents.build_embeddings", return_value=FakeEmbeddings()
        )
        embeddings.start()
        self.addCleanup(embeddings.stop)

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
        self.addCleanup(deps.get_default_archives.cache_clear)

        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://test"
        )
        self.addAsyncCleanup(self.client.aclose)

        self.owner = await deps.state_store.ensure_user(None)
        self.project = await deps.state_store.create_project(self.owner["id"], "Skyrim")

    async def asyncTearDown(self):
        # The turn writer is deferred and still holds state.db open, which is
        # WinError 32 when the tempdir is removed underneath it.
        await drain_deferred()
        self.tmp.cleanup()

    def _fakes(self, reply: str = "Greetings, thane.", chunks=None):
        return (
            patch.object(
                self.deps, "build_llm", new_callable=AsyncMock, return_value=_FakeLLM(reply)
            ),
            patch.object(
                self.deps,
                "get_archives_for_context",
                new_callable=AsyncMock,
                return_value=_StubArchives(chunks),
            ),
        )

    async def _post(self, body: dict, reply: str = "Greetings, thane.", chunks=None):
        build_llm, archives = self._fakes(reply, chunks)
        with build_llm, archives:
            return await self.client.post("/v1/chat", json=body)

    @staticmethod
    def _frames(text: str) -> list[dict]:
        return [
            json.loads(line[len("data: ") :])
            for line in text.splitlines()
            if line.startswith("data: ") and line != "data: [DONE]"
        ]

    async def test_absent_stream_flag_returns_the_unchanged_json_body(self):
        """Back-compat is a hard constraint: no flag, no change."""
        response = await self._post({"message": "Hello.", "project_id": self.project["id"]})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"].split(";")[0], "application/json")
        body = response.json()
        self.assertEqual(body["response"], "Greetings, thane.")
        self.assertTrue(body["success"])
        self.assertIn("thread_id", body)
        self.assertIn("sources", body)

    async def test_stream_true_returns_sse_frames(self):
        response = await self._post(
            {"message": "Hello.", "project_id": self.project["id"], "stream": True}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"].split(";")[0], "text/event-stream")

        frames = self._frames(response.text)
        self.assertEqual(frames[0]["object"], "sentient.chat.meta")
        self.assertIn("thread_id", frames[0])
        self.assertIn("sources", frames[0])

        chunks = [f for f in frames if f["object"] == "chat.completion.chunk"]
        text = "".join(c["choices"][0]["delta"].get("content", "") for c in chunks)
        self.assertEqual(text.strip(), "Greetings, thane.")
        self.assertTrue(response.text.rstrip().endswith("data: [DONE]"))

    async def test_the_meta_frame_carries_the_sources_the_lore_inspector_needs(self):
        """`sources` cannot be appended after the stream — the client renders as it
        reads — which is the whole reason a non-OpenAI first frame exists."""
        from langchain_core.documents import Document

        document = Document(
            page_content="Journeyman trainers cap a skill at 50.",
            metadata={"source": "skyrimskills.pdf", "page_label": "3", "chunk_id": 7},
        )
        response = await self._post(
            {"message": "Hello.", "project_id": self.project["id"], "stream": True},
            chunks=[(document, 0.74)],
        )

        meta = self._frames(response.text)[0]
        self.assertEqual(len(meta["sources"]), 1)
        self.assertEqual(meta["sources"][0]["source"], "skyrimskills.pdf")
        self.assertEqual(meta["sources"][0]["score"], 0.74)
        self.assertEqual(meta["sources"][0]["chunk_id"], 7)

    async def test_a_real_retrieval_encodes_into_the_meta_frame(self):
        """The one test here that does NOT stub the retriever.

        Every other case hands `_StubArchives` a hand-written score, and a Python
        float is exactly what the real backend could not produce: FAISS returns
        `numpy.float32`, `json.dumps` refuses it, and the turn 500'd. The stub was
        the reason a whole streaming suite stayed green through a broken wire.

        With an empty index `sources` is `[]` and the meta frame encodes fine, so
        the crash waited for a project to have lore. This indexes one document so
        retrieval actually returns something.
        """
        from langchain_core.documents import Document

        from sentient.adapters.documents import ArchivesIngestion

        archives = ArchivesIngestion()
        await archives.backend.index(
            [
                Document(
                    page_content="Journeyman trainers cap a skill at 50.",
                    metadata={"source": "skyrimskills.pdf", "page_label": "3", "chunk_id": 7},
                )
            ]
        )

        with (
            patch.object(
                self.deps, "build_llm", new_callable=AsyncMock, return_value=_FakeLLM("Aye.")
            ),
            patch.object(
                self.deps, "get_archives_for_context", new_callable=AsyncMock, return_value=archives
            ),
        ):
            response = await self.client.post(
                "/v1/chat",
                json={
                    "message": "What cap do journeyman trainers set?",
                    "project_id": self.project["id"],
                    "stream": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        meta = self._frames(response.text)[0]
        self.assertEqual(meta["sources"][0]["source"], "skyrimskills.pdf")
        self.assertIs(type(meta["sources"][0]["score"]), float)

    async def test_a_streamed_turn_is_persisted_like_a_non_streamed_one(self):
        response = await self._post(
            {"message": "Hello.", "project_id": self.project["id"], "stream": True}
        )
        thread_id = self._frames(response.text)[0]["thread_id"]
        await drain_deferred()

        messages = await self.deps.state_store.list_messages(thread_id, limit=10)
        self.assertEqual(
            [(m["role"], m["content"].strip()) for m in messages],
            [("user", "Hello."), ("assistant", "Greetings, thane.")],
        )

    async def test_streaming_without_a_project_is_rejected(self):
        """The projectless path uses NPCBrain.ask_with_context, which does not stream.

        A fake single-chunk stream would hide that from the console.
        """
        response = await self._post({"message": "Hi", "stream": True})

        self.assertEqual(response.status_code, 400)
        self.assertIn("project_id", response.json()["detail"])

    async def test_a_reindexing_project_is_still_409_when_streaming(self):
        """Grounding runs before the response starts, so the documented status
        survives. Raised from inside the generator it would arrive as a broken
        stream instead."""
        await self.deps.state_store.set_project_status(self.project["id"], "reindexing_required")

        response = await self._post(
            {"message": "Hello.", "project_id": self.project["id"], "stream": True}
        )

        self.assertEqual(response.status_code, 409)

    async def test_a_provider_failure_mid_stream_reaches_the_console(self):
        """The console shares the game path's error frame; H1 Finding 2 applies to
        both surfaces."""

        class _DyingLLM(_FakeLLM):
            async def astream(self, messages):
                class _Chunk:
                    content = "Greet"

                yield _Chunk()
                raise RuntimeError("Error code: 402 - payment_required")

        with (
            patch.object(
                self.deps,
                "build_llm",
                new_callable=AsyncMock,
                return_value=_DyingLLM("unused"),
            ),
            patch.object(
                self.deps,
                "get_archives_for_context",
                new_callable=AsyncMock,
                return_value=_StubArchives(),
            ),
        ):
            response = await self.client.post(
                "/v1/chat",
                json={"message": "Hello.", "project_id": self.project["id"], "stream": True},
            )

        errors = [f for f in self._frames(response.text) if "error" in f]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["error"]["type"], "provider_error")


if __name__ == "__main__":
    unittest.main()
