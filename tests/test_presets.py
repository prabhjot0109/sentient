from __future__ import annotations

import unittest

from sentient.core.presets import get_preset, list_presets


class PresetTests(unittest.TestCase):
    def test_builtin_presets_available(self):
        names = list_presets()
        self.assertIn("skyrim", names)
        self.assertIn("fallout4", names)

    def test_get_preset_returns_nonempty_template(self):
        self.assertIn("Skyrim", get_preset("skyrim"))
        self.assertIn("Fallout", get_preset("fallout4"))

    def test_unknown_preset_is_empty(self):
        self.assertEqual(get_preset("witcher"), "")


if __name__ == "__main__":
    unittest.main()
