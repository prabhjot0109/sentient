from __future__ import annotations

import json
import unittest


class _FakeStreamLLM:
    async def astream(self, messages):
        for piece in ["Hello", ", ", "traveler."]:

            class _Response:
                content = piece

            yield _Response()


class AstreamCompletionTests(unittest.IsolatedAsyncioTestCase):
    async def test_emits_openai_sse_chunks_and_done(self):
        from sentient.adapters.llm.openai_wire import astream_completion

        chunks = [chunk async for chunk in astream_completion(_FakeStreamLLM(), [], "model-x")]

        self.assertTrue(chunks[0].startswith("data: "))
        self.assertEqual(chunks[-1], "data: [DONE]\n\n")
        text = ""
        for chunk in chunks:
            payload = chunk[len("data: ") :].strip()
            if not payload or payload == "[DONE]":
                continue
            text += json.loads(payload)["choices"][0]["delta"].get("content", "")
        self.assertEqual(text, "Hello, traveler.")


class _ScriptedStreamLLM:
    """Same idiom as _FakeStreamLLM above, with the pieces supplied per test."""

    def __init__(self, *pieces: str):
        self._pieces = pieces

    async def astream(self, messages):
        for piece in self._pieces:

            class _Response:
                content = piece

            yield _Response()


class _FailingStreamLLM:
    """Yields `pieces`, then raises the way a provider does mid-response.

    Cerebras returning 402 payment_required is the case H1 measured; the class of
    failure is anything the SDK raises once the first token is already on the wire.
    """

    def __init__(self, *pieces: str, error: Exception | None = None):
        self._pieces = pieces
        self._error = error or RuntimeError("Error code: 402 - payment_required")

    async def astream(self, messages):
        for piece in self._pieces:

            class _Response:
                content = piece

            yield _Response()
        raise self._error


def _frames(events: list[str]) -> list[dict]:
    payloads = [event[len("data: ") :].strip() for event in events]
    return [json.loads(p) for p in payloads if p and p != "[DONE]"]


class MidStreamProviderFailureTests(unittest.IsolatedAsyncioTestCase):
    """H1 Finding 2: a provider error mid-stream arrived as a successful empty reply.

    HTTP 200 is already committed once the first frame flushes, so the only place
    the failure can be reported is in-band. The shape is the one the OpenAI SDK
    already raises on, which is what makes Mantella able to tell an outage from an
    NPC with nothing to say.
    """

    async def test_the_error_reaches_the_client_as_a_frame(self):
        from sentient.adapters.llm.openai_wire import astream_completion

        events = [
            event
            async for event in astream_completion(
                _FailingStreamLLM("Greet", "ings, "), [], "model-x"
            )
        ]

        error_frames = [f for f in _frames(events) if "error" in f]
        self.assertEqual(len(error_frames), 1, "exactly one error frame")
        error = error_frames[0]["error"]
        self.assertIn("402", error["message"])
        self.assertEqual(error["type"], "provider_error")
        self.assertEqual(error["code"], "RuntimeError")
        self.assertEqual(error_frames[0]["object"], "error")

    async def test_the_tokens_that_did_arrive_are_kept_and_the_stream_terminates(self):
        from sentient.adapters.llm.openai_wire import astream_completion

        events = [
            event
            async for event in astream_completion(
                _FailingStreamLLM("Greet", "ings, "), [], "model-x"
            )
        ]

        text = "".join(
            frame["choices"][0]["delta"].get("content", "")
            for frame in _frames(events)
            if frame.get("object") == "chat.completion.chunk"
        )
        self.assertEqual(text, "Greetings, ")
        self.assertEqual(events[-1], "data: [DONE]\n\n")

    async def test_a_failed_stream_never_claims_it_stopped_normally(self):
        """finish_reason "stop" on a truncated reply is the lie that made this
        indistinguishable from a short answer."""
        from sentient.adapters.llm.openai_wire import astream_completion

        events = [
            event async for event in astream_completion(_FailingStreamLLM("Greet"), [], "model-x")
        ]

        reasons = [
            frame["choices"][0]["finish_reason"]
            for frame in _frames(events)
            if frame.get("object") == "chat.completion.chunk"
        ]
        self.assertNotIn("stop", reasons)

    async def test_the_partial_reply_still_reaches_on_reply(self):
        """The player heard those tokens, so the transcript has to keep them."""
        from sentient.adapters.llm.openai_wire import astream_completion

        captured: list[str] = []
        async for _ in astream_completion(
            _FailingStreamLLM("Greet", "ings, "),
            [],
            "model-x",
            on_reply=lambda reply, _chunk: captured.append(reply),
        ):
            pass

        self.assertEqual(captured, ["Greetings, "])

    async def test_the_failure_is_logged_with_the_model(self):
        """The traceback went only to the console before; nothing named the model."""
        from sentient.adapters.llm import openai_wire

        with self.assertLogs("sentient.adapters.llm.openai_wire", level="ERROR") as logs:
            async for _ in openai_wire.astream_completion(_FailingStreamLLM("Hi"), [], "model-x"):
                pass

        self.assertEqual(logs.records[0].model, "model-x")
        self.assertIsNotNone(logs.records[0].exc_info)

    async def test_a_successful_stream_is_unchanged(self):
        """Back-compat: the working path must not gain or lose a frame."""
        from sentient.adapters.llm.openai_wire import astream_completion

        events = [
            event
            async for event in astream_completion(
                _ScriptedStreamLLM("Greet", "ings."), [], "model-x"
            )
        ]

        frames = _frames(events)
        self.assertTrue(all("error" not in frame for frame in frames))
        self.assertEqual(frames[-1]["choices"][0]["finish_reason"], "stop")
        self.assertEqual(events[-1], "data: [DONE]\n\n")


class StreamedReplyCaptureTests(unittest.IsolatedAsyncioTestCase):
    """G4 persists the assistant side of a streamed turn, so the reply text has
    to leave the stream. It is joined after the last token, never per token."""

    async def test_on_complete_receives_the_whole_reply(self):
        from sentient.services.chat import stream_completion

        captured: list[str] = []
        events = [
            event
            async for event in stream_completion(
                _ScriptedStreamLLM("Greet", "ings, ", "thane."),
                [],
                "test-model",
                on_complete=lambda reply, _usage: captured.append(reply),
            )
        ]

        self.assertEqual(captured, ["Greetings, thane."])
        self.assertTrue(events[-1].startswith("data: [DONE]"))

    async def test_on_complete_receives_an_empty_string_when_nothing_streamed(self):
        from sentient.services.chat import stream_completion

        captured: list[str] = []
        async for _ in stream_completion(
            _ScriptedStreamLLM(),
            [],
            "test-model",
            on_complete=lambda reply, _usage: captured.append(reply),
        ):
            pass

        self.assertEqual(captured, [""])


if __name__ == "__main__":
    unittest.main()
