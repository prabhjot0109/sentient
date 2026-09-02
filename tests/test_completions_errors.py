"""B4: a provider failure must reach the client as a readable, OpenAI-shaped error."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace

from fastapi import HTTPException
from fastapi.testclient import TestClient

from sentient.adapters.llm.openai_wire import error_body, error_event
from sentient.api import deps
from sentient.api.app import app
from sentient.services.runtime import RuntimeContext


class ErrorBodyTests(unittest.TestCase):
    def test_body_carries_the_providers_own_words(self):
        body = error_body(RuntimeError("payment_required: visit your billing tab"))
        self.assertEqual(body["object"], "error")
        self.assertEqual(body["error"]["message"], "payment_required: visit your billing tab")
        self.assertEqual(body["error"]["type"], "provider_error")
        self.assertEqual(body["error"]["code"], "RuntimeError")

    def test_a_message_less_exception_still_names_its_class(self):
        # A bare exception str()s to "", and an empty message tells the player
        # nothing at all -- which is the defect this whole plan exists to fix.
        body = error_body(TimeoutError())
        self.assertEqual(body["error"]["message"], "TimeoutError")

    def test_a_provider_html_error_page_is_truncated(self):
        body = error_body(RuntimeError("x" * 5000))
        self.assertEqual(len(body["error"]["message"]), 500)

    def test_the_sse_frame_is_the_same_payload_framed(self):
        # error_event's output is a public contract already shipped in 134741e.
        # It must not change shape now that it shares a builder.
        exc = RuntimeError("boom")
        frame = error_event(exc)
        self.assertTrue(frame.startswith("data: "))
        self.assertTrue(frame.endswith("\n\n"))
        self.assertEqual(json.loads(frame[len("data: ") :]), error_body(exc))


class _DeadProvider:
    """An LLM whose ainvoke fails the way a 402 from Cerebras fails."""

    async def ainvoke(self, messages, config=None):
        raise RuntimeError("Error code: 402 - payment_required: Visit your billing tab.")


class _EmptyArchives:
    """Grounding is best-effort and irrelevant here; return nothing, quickly."""

    async def retrieve(self, *args, **kwargs):
        return []


def _stub_ctx(project_id: str | None = None) -> RuntimeContext:
    return RuntimeContext(
        user_key="probe",
        user_id="probe-user",
        project_id=project_id,
        session_id=None,
        llm_settings={"provider": "groq", "model": "model-x"},
        rag_settings={
            "top_k": 4,
            "search_type": "similarity",
            "score_threshold": 0.0,
            "embedding_provider": "fake",
            "embedding_model": "fake",
            "mrl_vector_size": None,
        },
        system_prompt="You are a probe.",
        config_signature="probe-signature",
    )


class CompletionsErrorRouteTests(unittest.TestCase):
    """The two Mantella-shaped routes had NO exception handling at all, so a
    provider failure escaped to Starlette and rendered a bare `Internal Server
    Error` as text/plain with no body. Measured 2026-08-23."""

    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)
        # deps is patched as a MODULE attribute, never imported by name -- the
        # name form binds at import time and the router would keep the real one.
        self._real = {
            name: getattr(deps, name)
            for name in ("get_llm", "completions_ctx", "get_archives_for_context", "_settings")
        }

        async def _fake_get_llm(ctx):
            return _DeadProvider()

        async def _fake_ctx(api_key, project_id):
            return _stub_ctx(project_id)

        async def _fake_archives(ctx):
            return _EmptyArchives()

        deps.get_llm = _fake_get_llm
        deps.completions_ctx = _fake_ctx
        deps.get_archives_for_context = _fake_archives
        # Condensing would call the dead LLM inside prepare_completion instead of
        # at the invoke this test is about. Pin it off so the failure has one site.
        deps._settings = replace(deps._settings, condense_queries=False)

    def tearDown(self):
        for name, value in self._real.items():
            setattr(deps, name, value)

    def _post(self, path):
        return self.client.post(
            path, json={"messages": [{"role": "user", "content": "Who are you?"}]}
        )

    def test_key_route_reports_the_provider_instead_of_a_bare_500(self):
        response = self._post("/v1/sk-sent-probe/chat/completions")
        self.assertEqual(response.status_code, 502)
        body = response.json()
        self.assertEqual(body["object"], "error")
        self.assertIn("402", body["error"]["message"])

    def test_key_and_project_route_reports_the_provider(self):
        response = self._post(
            "/v1/sk-sent-probe/00000000-0000-0000-0000-000000000000/chat/completions"
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["object"], "error")

    def test_env_default_route_reports_the_provider(self):
        response = self._post("/v1/chat/completions")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["object"], "error")

    def test_an_ownership_404_is_not_flattened_into_a_500(self):
        # R7's delta: a blanket `except Exception -> 500` on these routes once
        # swallowed the ownership HTTPExceptions and turned every 404 into a 500.
        # `except HTTPException: raise` must stay first.
        async def _not_found(api_key, project_id):
            raise HTTPException(status_code=404, detail="project not found")

        deps.completions_ctx = _not_found
        response = self._post("/v1/sk-sent-probe/nope/chat/completions")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
