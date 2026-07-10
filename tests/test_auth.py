from __future__ import annotations

import hashlib
import unittest

from logic.auth import generate_api_key, hash_key, user_key_of


class KeyPrimitiveTests(unittest.TestCase):
    def test_hash_key_is_sha256_hex(self):
        self.assertEqual(hash_key("abc"), hashlib.sha256(b"abc").hexdigest())

    def test_user_key_is_short_and_stable_and_opaque(self):
        uk = user_key_of("super-secret-key")
        self.assertEqual(len(uk), 16)
        self.assertNotIn("secret", uk)
        self.assertEqual(uk, user_key_of("super-secret-key"))

    def test_generate_api_key_prefixed_and_hash_matches(self):
        raw, h = generate_api_key()
        self.assertTrue(raw.startswith("sk-sent-"))
        self.assertEqual(h, hash_key(raw))
        raw2, _ = generate_api_key()
        self.assertNotEqual(raw, raw2)  # random


if __name__ == "__main__":
    unittest.main()
