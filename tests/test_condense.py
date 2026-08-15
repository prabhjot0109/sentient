from __future__ import annotations

import unittest

from sentient.services.condense import needs_condensation


class PronounGateTests(unittest.TestCase):
    def test_pronoun_queries_need_condensation(self):
        for q in ["What skills do they have?", "Tell me about them.",
                  "Where is it located?", "Who are those people?"]:
            self.assertTrue(needs_condensation(q), q)

    def test_standalone_queries_bypass(self):
        for q in ["What skills do Nords have?", "Where is Whiterun?",
                  "Describe the Thieves Guild.", "Hello"]:
            self.assertFalse(needs_condensation(q), q)

    def test_word_boundary_not_substring(self):
        # "item" contains "it" but must NOT trigger.
        self.assertFalse(needs_condensation("What is this item?"))
        self.assertFalse(needs_condensation("Tell me about the pheasant."))  # "he" substring


import unittest as _ut
from langchain_core.messages import AIMessage, HumanMessage


class _FakeLLM:
    def __init__(self, reply): self._reply = reply; self.calls = 0
    async def ainvoke(self, messages):
        self.calls += 1
        class _R: content = self._reply
        return _R()


class CondenseQueryTests(_ut.IsolatedAsyncioTestCase):
    async def test_bypass_when_no_pronoun_makes_no_llm_call(self):
        from sentient.services.condense import condense_query
        llm = _FakeLLM("SHOULD NOT BE USED")
        out = await condense_query(llm, [], "What skills do Nords have?")
        self.assertEqual(out, "What skills do Nords have?")
        self.assertEqual(llm.calls, 0)

    async def test_rewrites_when_pronoun_present(self):
        from sentient.services.condense import condense_query
        llm = _FakeLLM("What skills do Nords have?")
        history = [HumanMessage(content="What skills do Nords have?"),
                   AIMessage(content="Nords are strong warriors.")]
        out = await condense_query(llm, history, "What skills do they have?")
        self.assertEqual(out, "What skills do Nords have?")
        self.assertEqual(llm.calls, 1)

    async def test_llm_error_falls_back_to_original(self):
        from sentient.services.condense import condense_query
        class _Boom:
            async def ainvoke(self, m): raise RuntimeError("boom")
        out = await condense_query(_Boom(), [HumanMessage(content="x")], "where is it?")
        self.assertEqual(out, "where is it?")


class ToHistoryTests(unittest.TestCase):
    def test_to_history_excludes_final_user_turn(self):
        from sentient.adapters.llm.openai_wire import OpenAIMessage, to_history
        msgs = [OpenAIMessage(role="system", content="You are Lydia."),
                OpenAIMessage(role="user", content="What skills do Nords have?"),
                OpenAIMessage(role="assistant", content="Strong warriors."),
                OpenAIMessage(role="user", content="What skills do they have?")]
        hist = to_history(msgs)
        # last user turn is the query, not part of history
        self.assertEqual(len(hist), 3)
        self.assertEqual(hist[-1].content, "Strong warriors.")


if __name__ == "__main__":
    unittest.main()
