from __future__ import annotations

import unittest

from logic.condense import needs_condensation


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


if __name__ == "__main__":
    unittest.main()
