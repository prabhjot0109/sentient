from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

import httpx
from langchain_core.embeddings import Embeddings


class FakeEmbeddings(Embeddings):
    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 1.0, 0.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


class ExplodingStore:
    """Every call fails, the way an unreachable database behaves.

    Not a Mock: a Mock returns a Mock for `list_projects`, and awaiting that
    raises TypeError rather than the connection error the probe is meant to
    catch, which would make the test pass for the wrong reason.
    """

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error or ConnectionRefusedError("no route to the database")

    async def list_projects(self, user_id: str):
        raise self.error


class ReadinessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {"DATA_DIR": self.tmp.name, "VECTOR_BACKEND": "faiss"})
        env.start()
        self.addCleanup(env.stop)

        embeddings = patch(
            "sentient.adapters.documents.build_embeddings", return_value=FakeEmbeddings()
        )
        embeddings.start()
        self.addCleanup(embeddings.stop)

        from sentient.adapters.state import get_state_store
        from sentient.api import app as api
        from sentient.api import deps
        from sentient.core.config import load_rag_settings

        self.deps = deps
        deps._settings = load_rag_settings()
        deps.state_store = get_state_store(deps._settings)
        deps.get_default_archives.cache_clear()
        self.addCleanup(deps.get_default_archives.cache_clear)

        self.healthy_store = deps.state_store
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://test"
        )
        self.addAsyncCleanup(self.client.aclose)

    def _break_the_store(self, error: Exception | None = None) -> None:
        self.deps.state_store = ExplodingStore(error)
        self.addCleanup(setattr, self.deps, "state_store", self.healthy_store)

    async def test_ready_when_the_store_answers(self):
        response = await self.client.get("/health/ready")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["checks"]["state_store"], "ok")

    async def test_not_ready_when_the_store_raises(self):
        self._break_the_store()

        response = await self.client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["ready"])

    async def test_the_failing_check_is_named_in_the_body(self):
        """An unnamed 503 sends the operator to the logs for something the probe
        already knew."""
        self._break_the_store(ConnectionRefusedError("no route to the database"))

        payload = (await self.client.get("/health/ready")).json()

        self.assertIn("ConnectionRefusedError", payload["checks"]["state_store"])

    async def test_liveness_still_answers_when_the_store_is_down(self):
        """`/health` must NOT start failing.

        It is liveness, and a database outage is not a reason to restart the
        process. Conflating the two is how a slow database becomes a restart loop.
        """
        self._break_the_store()

        response = await self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "online")

    async def test_readiness_does_not_call_a_provider(self):
        """A probe that costs an LLM call bills on a 30-second timer forever, and
        takes the service out of rotation whenever the provider has a bad minute."""
        from sentient.adapters.llm import models

        with (
            patch.object(models, "build_chat_model") as chat,
            patch("sentient.adapters.documents.build_embeddings") as embeddings,
        ):
            await self.client.get("/health/ready")

        chat.assert_not_called()
        embeddings.assert_not_called()

    async def test_queue_depth_is_reported(self):
        """Depth is the one number that predicts the stuck-ingest failure mode, and
        no other surface carries it."""
        payload = (await self.client.get("/health/ready")).json()

        self.assertEqual(payload["checks"]["ingest_queue_depth"], 0)
        self.assertEqual(payload["checks"]["reindex_queue_depth"], 0)

    async def test_a_deep_queue_is_still_ready(self):
        """Reported, not asserted on.

        A deep queue is busy, not unhealthy. Failing readiness on it would pull the
        instance out of rotation exactly when it has the most work in flight.
        """
        with patch.object(self.deps.ingest_queue, "depth", return_value=63):
            response = await self.client.get("/health/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["checks"]["ingest_queue_depth"], 63)


if __name__ == "__main__":
    unittest.main()
