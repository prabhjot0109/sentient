"""B4: a provider failure must reach the client as a readable, OpenAI-shaped error."""

from __future__ import annotations

import json
import unittest

from sentient.adapters.llm.openai_wire import error_body, error_event


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


if __name__ == "__main__":
    unittest.main()
