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
                on_complete=captured.append,
            )
        ]

        self.assertEqual(captured, ["Greetings, thane."])
        self.assertTrue(events[-1].startswith("data: [DONE]"))

    async def test_on_complete_receives_an_empty_string_when_nothing_streamed(self):
        from sentient.services.chat import stream_completion

        captured: list[str] = []
        async for _ in stream_completion(
            _ScriptedStreamLLM(), [], "test-model", on_complete=captured.append
        ):
            pass

        self.assertEqual(captured, [""])


if __name__ == "__main__":
    unittest.main()
