from __future__ import annotations

import unittest

from sentient.core.presets import PRESETS, get_preset, list_presets


class PresetTests(unittest.TestCase):
    def test_builtin_presets_available(self):
        names = list_presets()
        self.assertIn("skyrim", names)
        self.assertIn("fallout4", names)
        self.assertIn("fantasy", names)
        self.assertIn("scifi", names)
        self.assertIn("cyberpunk", names)

    def test_get_preset_returns_nonempty_template(self):
        self.assertIn("Skyrim", get_preset("skyrim"))
        self.assertIn("Fallout", get_preset("fallout4"))

    def test_unknown_preset_is_empty(self):
        self.assertEqual(get_preset("witcher"), "")

    def test_every_preset_forbids_breaking_character(self):
        """The rule that stops an NPC answering a meta question as an assistant.

        Asserted over the dict rather than per preset, so the next one added is
        covered without anyone remembering to extend this file. It is the whole
        reason a preset is better than an empty persona.
        """
        for name, template in PRESETS.items():
            with self.subTest(preset=name):
                self.assertIn("Never mention the real world", template)
                self.assertIn("AI", template)

    def test_every_preset_asks_for_a_spoken_length(self):
        """Replies are voiced. Mantella trims to `max_response_sentences_single`,
        so a model that writes five paragraphs has paid the latency and had the
        result discarded."""
        for name, template in PRESETS.items():
            with self.subTest(preset=name):
                self.assertIn("1-3 sentences", template)

    def test_the_list_is_sorted_and_lowercase(self):
        """`get_preset` lowercases its argument, so a mixed-case key would be
        listed by the API and then never resolve."""
        names = list_presets()
        self.assertEqual(names, sorted(names))
        self.assertTrue(all(name == name.lower() for name in names))


if __name__ == "__main__":
    unittest.main()
