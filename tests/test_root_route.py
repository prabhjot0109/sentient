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


class RootRouteTests(unittest.IsolatedAsyncioTestCase):
    """`GET /` exists because a platform's port scanner asks for it.

    Measured on Render 2026-08-31. The container started correctly and uvicorn
    logged `Uvicorn running on http://0.0.0.0:8000`, the health check at
    /health/ready answered 200 every five seconds, and the deploy was marked live.
    The service was still unreachable from the internet, answering every public
    request with a 404 carrying `x-render-routing: no-server`.

    The build log has the whole story in three lines:

        INFO:  127.0.0.1:55954 - "HEAD / HTTP/1.1" 404 Not Found
        ==>   No open ports detected, continuing to scan...
        ==>   Your service is live

    The scanner probes `HEAD /`, treated the 404 as "nothing serving here", and
    never added the port to the routing table. Liveness and routing are decided
    separately, so the service reported healthy while receiving no traffic -- the
    failure looks like a broken app and is a missing route.

    So the fix is not a workaround. A base URL that answers nothing is a dead end
    for anyone who pastes it into a browser, and this is also the first thing a
    Mantella user sees if they trim the path by accident.
    """

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

        from sentient.api import app as api
        from sentient.api import deps

        deps.get_default_archives.cache_clear()
        self.addCleanup(deps.get_default_archives.cache_clear)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://test"
        )
        self.addAsyncCleanup(self.client.aclose)

    async def test_the_root_answers_200(self):
        response = await self.client.get("/")

        self.assertEqual(response.status_code, 200)

    async def test_head_on_the_root_answers_200(self):
        """The probe uses HEAD, not GET.

        Starlette routes HEAD to the GET handler, so this passes for free -- but it
        is the exact request the scanner makes, and asserting GET alone would not
        have caught a route registered for GET only.
        """
        response = await self.client.head("/")

        self.assertEqual(response.status_code, 200)

    async def test_it_names_the_service_and_points_at_the_docs(self):
        """A human who pastes the base URL into a browser should learn where to go."""
        payload = (await self.client.get("/")).json()

        self.assertEqual(payload["service"], "sentient")
        self.assertEqual(payload["docs"], "/docs")
        self.assertEqual(payload["health"], "/health/ready")

    async def test_it_reveals_nothing_about_the_deployment(self):
        """Unauthenticated and public, so it carries no configuration.

        `/health` already reports providers and models to anyone who asks, which is
        its own question; this route must not widen that surface. No provider, no
        model, no database host, no key.
        """
        body = (await self.client.get("/")).text.lower()

        for leak in ("groq", "google", "postgres", "neon", "qdrant", "key", "sk-"):
            self.assertNotIn(leak, body)

    async def test_it_does_not_touch_the_database(self):
        """The scanner hits this before anything is warm, and on every restart.

        A root route that queried the store would turn a database blip into a
        service that never gets added to the routing table at all.
        """
        from sentient.api import deps

        class ExplodingStore:
            async def list_projects(self, user_id: str):
                raise ConnectionRefusedError("the database is down")

        original = deps.state_store
        deps.state_store = ExplodingStore()
        self.addCleanup(setattr, deps, "state_store", original)

        self.assertEqual((await self.client.get("/")).status_code, 200)


if __name__ == "__main__":
    unittest.main()
