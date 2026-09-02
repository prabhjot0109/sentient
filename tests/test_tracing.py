"""H8. A tracer that can break the product it observes is worse than no tracer.

`get_trace_handler` sits on the request path, so every one of these tests is
about the same rule stated four ways: whatever goes wrong -- the package is not
installed, the keys are absent, the host is unreachable, the constructor raises
-- the answer is `None` and chat is unaffected.

The no-op path is the one that runs in every fresh clone and every CI job, so it
is the one that must be pinned hardest.
"""

from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from sentient.adapters import tracing
from sentient.core.config import load_rag_settings


def _settings(**overrides):
    return replace(load_rag_settings(), **overrides)


def _configured(**overrides):
    return _settings(
        **{
            "langfuse_enabled": True,
            "langfuse_public_key": "pk-lf-test",
            "langfuse_secret_key": "sk-lf-test",
            "langfuse_host": "https://cloud.langfuse.test",
            **overrides,
        }
    )


class TraceHandlerTests(unittest.TestCase):
    def setUp(self):
        # Resolution is memoised for the life of the process, so every test has to
        # start from unresolved or the first one decides the answer for the rest.
        tracing.reset_trace_handler()
        self.addCleanup(tracing.reset_trace_handler)

    def test_disabled_by_default(self):
        """Defaults preserve behavior. A fresh clone traces nothing."""
        self.assertIsNone(tracing.get_trace_handler(_settings()))

    def test_enabled_with_no_keys_is_still_off(self):
        """Half-configured is off, not half-on. The SDK would otherwise fall back
        to reading LANGFUSE_* out of the environment itself, which would put a
        second, invisible configuration source beside core/config.py."""
        self.assertIsNone(
            tracing.get_trace_handler(_configured(langfuse_public_key="", langfuse_secret_key=""))
        )

    def test_returns_none_when_the_import_is_missing(self):
        """`langfuse` is optional. An ImportError must not take down the app: the
        observability tool cannot be a startup dependency of what it observes."""
        with patch.object(tracing, "_construct_handler", side_effect=ImportError("no langfuse")):
            self.assertIsNone(tracing.get_trace_handler(_configured()))

    def test_returns_none_when_construction_raises(self):
        """A bad key, an unreachable host. Same rule, and the same for anything
        the SDK invents later -- which is why the guard catches Exception rather
        than an enumerated list the next release can fall outside of."""
        with patch.object(tracing, "_construct_handler", side_effect=RuntimeError("401")):
            self.assertIsNone(tracing.get_trace_handler(_configured()))

    def test_it_is_constructed_once_and_reused(self):
        """Per-request construction opens a client per turn, which is the opposite
        of what a callback handler is for."""
        sentinel = object()
        with patch.object(tracing, "_construct_handler", return_value=sentinel) as build:
            first = tracing.get_trace_handler(_configured())
            second = tracing.get_trace_handler(_configured())

        self.assertIs(first, sentinel)
        self.assertIs(second, sentinel)
        self.assertEqual(build.call_count, 1)

    def test_a_failure_is_not_retried_on_every_turn(self):
        """The expensive failure is the slow one: an unreachable host retried per
        request adds its timeout to every NPC line. Resolution is memoised even
        when the answer is None."""
        with patch.object(tracing, "_construct_handler", side_effect=RuntimeError("down")) as build:
            self.assertIsNone(tracing.get_trace_handler(_configured()))
            self.assertIsNone(tracing.get_trace_handler(_configured()))

        self.assertEqual(build.call_count, 1)

    def test_the_credentials_reach_the_constructor(self):
        with patch.object(tracing, "_construct_handler", return_value=object()) as build:
            tracing.get_trace_handler(_configured())

        settings = build.call_args.args[0]
        self.assertEqual(settings.langfuse_public_key, "pk-lf-test")
        self.assertEqual(settings.langfuse_secret_key, "sk-lf-test")
        self.assertEqual(settings.langfuse_host, "https://cloud.langfuse.test")


class TraceConfigTests(unittest.TestCase):
    """`trace_config` is what call sites use, so the shape it returns when tracing
    is off has to be exactly what those call sites passed before H8 existed."""

    def setUp(self):
        tracing.reset_trace_handler()
        self.addCleanup(tracing.reset_trace_handler)

    def test_it_is_none_when_the_handler_is_none(self):
        """`config=None` is LangChain's own default, so the off path is
        byte-identical to the code that ran before this feature -- which is what
        makes "defaults preserve behavior" true rather than merely intended."""
        self.assertIsNone(tracing.trace_config(_settings()))

    def test_it_carries_the_handler_when_there_is_one(self):
        sentinel = object()
        with patch.object(tracing, "_construct_handler", return_value=sentinel):
            self.assertEqual(tracing.trace_config(_configured()), {"callbacks": [sentinel]})


class RagInvokesWithoutCallbacksWhenTracingIsOffTests(unittest.IsolatedAsyncioTestCase):
    """The no-op path, asserted at the call site rather than only at the seam."""

    def setUp(self):
        tracing.reset_trace_handler()
        self.addCleanup(tracing.reset_trace_handler)

    async def test_the_llm_fallback_receives_config_none(self):
        from sentient.services.rag import NPCBrain

        brain = NPCBrain.__new__(NPCBrain)
        brain.settings = _settings()

        captured: dict[str, object] = {}

        class _Result:
            content = "I have nothing to say about that."

        class _LLM:
            async def ainvoke(self, messages, config=None):
                captured["config"] = config
                return _Result()

        class _Prompt:
            def format_prompt(self, **kwargs):
                class _P:
                    def to_messages(self_inner):
                        return []

                return _P()

        class _Ingestion:
            async def retrieve(self, question, k=None):
                return []

        brain.llm = _LLM()
        brain.prompt = _Prompt()
        brain.ingestion = _Ingestion()
        brain.document_prompt = None

        with patch.object(NPCBrain, "_build_document_chain", return_value=None):
            result = await brain.ask_with_context("who is Thornwald?")

        self.assertEqual(result["answer"], "I have nothing to say about that.")
        self.assertIsNone(captured["config"])


if __name__ == "__main__":
    unittest.main()
