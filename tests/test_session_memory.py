from __future__ import annotations

import unittest

from langchain_core.messages import AIMessage, HumanMessage

from sentient.services.memory import SessionMemory


class SessionMemoryTests(unittest.TestCase):
    def test_history_scoped_by_session_and_npc(self):
        mem = SessionMemory(max_turns=10)
        mem.append("s1", "Lydia", "user", "hello Lydia")
        mem.append("s1", "Lydia", "assistant", "hello thane")
        mem.append("s1", "Balgruuf", "user", "my jarl")
        self.assertEqual(len(mem.history("s1", "Lydia")), 2)
        self.assertEqual(len(mem.history("s1", "Balgruuf")), 1)
        self.assertEqual(mem.history("s2", "Lydia"), [])

    def test_rolling_window_evicts_oldest(self):
        mem = SessionMemory(max_turns=2)
        for i in range(5):
            mem.append("s1", "Lydia", "user", f"msg{i}")
        hist = mem.history("s1", "Lydia")
        self.assertEqual(len(hist), 2)
        self.assertEqual(hist[-1].content, "msg4")

    def test_message_types_roundtrip(self):
        mem = SessionMemory()
        mem.append("s", "n", "user", "q")
        mem.append("s", "n", "assistant", "a")
        hist = mem.history("s", "n")
        self.assertIsInstance(hist[0], HumanMessage)
        self.assertIsInstance(hist[1], AIMessage)

    def test_clear(self):
        mem = SessionMemory()
        mem.append("s", "n", "user", "q")
        mem.clear("s", "n")
        self.assertEqual(mem.history("s", "n"), [])


if __name__ == "__main__":
    unittest.main()
