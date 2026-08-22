from __future__ import annotations

import unittest

from sentient.adapters.llm.openai_wire import OpenAIMessage
from sentient.services.chat import conversation_prefix_hash, conversation_prefix_hash_after


def _msgs(*pairs: tuple[str, str]) -> list[OpenAIMessage]:
    return [OpenAIMessage(role=role, content=content) for role, content in pairs]


class ConversationPrefixHashTests(unittest.TestCase):
    """The hash is the whole of G4's design: turn N's 'after' hash must equal
    turn N+1's 'before' hash, or every turn opens a new thread."""

    def test_first_turn_has_no_prefix(self):
        messages = _msgs(("system", "You are Lydia."), ("user", "Hello."))
        self.assertIsNone(conversation_prefix_hash(messages))

    def test_the_after_hash_of_turn_n_is_the_before_hash_of_turn_n_plus_1(self):
        turn_one = _msgs(("system", "You are Lydia."), ("user", "Hello."))
        after_one = conversation_prefix_hash_after(turn_one, "Greetings, thane.")

        turn_two = _msgs(
            ("system", "You are Lydia."),
            ("user", "Hello."),
            ("assistant", "Greetings, thane."),
            ("user", "Where are we?"),
        )
        self.assertEqual(conversation_prefix_hash(turn_two), after_one)

    def test_it_holds_across_three_turns(self):
        turn_two = _msgs(
            ("system", "You are Lydia."),
            ("user", "Hello."),
            ("assistant", "Greetings, thane."),
            ("user", "Where are we?"),
        )
        after_two = conversation_prefix_hash_after(turn_two, "Whiterun, my thane.")

        turn_three = _msgs(
            ("system", "You are Lydia."),
            ("user", "Hello."),
            ("assistant", "Greetings, thane."),
            ("user", "Where are we?"),
            ("assistant", "Whiterun, my thane."),
            ("user", "Lead on."),
        )
        self.assertEqual(conversation_prefix_hash(turn_three), after_two)

    def test_the_system_prompt_does_not_affect_the_hash(self):
        """Persona edits between turns must not fork the conversation."""
        first = _msgs(
            ("system", "You are Lydia."),
            ("user", "Hello."),
            ("assistant", "Greetings."),
            ("user", "Again?"),
        )
        second = _msgs(
            ("system", "You are Lydia, housecarl of Whiterun."),
            ("user", "Hello."),
            ("assistant", "Greetings."),
            ("user", "Again?"),
        )
        self.assertEqual(conversation_prefix_hash(first), conversation_prefix_hash(second))

    def test_a_diverged_conversation_hashes_differently(self):
        first = _msgs(("user", "Hello."), ("assistant", "Greetings."), ("user", "Where are we?"))
        second = _msgs(("user", "Hello."), ("assistant", "Well met."), ("user", "Where are we?"))
        self.assertNotEqual(conversation_prefix_hash(first), conversation_prefix_hash(second))

    def test_role_and_content_cannot_be_confused_across_the_boundary(self):
        """A naive join lets 'user'+'ab' and 'usera'+'b' collide."""
        first = _msgs(("user", "ab"), ("user", "x"))
        second = _msgs(("user", "a"), ("user", "b"), ("user", "x"))
        self.assertNotEqual(conversation_prefix_hash(first), conversation_prefix_hash(second))

    def test_none_content_is_treated_as_empty(self):
        messages = [
            OpenAIMessage(role="user", content=None),
            OpenAIMessage(role="assistant", content="hi"),
            OpenAIMessage(role="user", content="next"),
        ]
        self.assertIsNotNone(conversation_prefix_hash(messages))


if __name__ == "__main__":
    unittest.main()
