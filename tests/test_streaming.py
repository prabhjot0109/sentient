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


if __name__ == "__main__":
    unittest.main()
