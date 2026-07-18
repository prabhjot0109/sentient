from __future__ import annotations

import unittest


class EmbeddingSignatureTests(unittest.TestCase):
    def test_signature_stable_and_dimension_sensitive(self) -> None:
        from logic.runtime import embedding_signature

        base = {
            "embedding_provider": "google",
            "embedding_model": "models/gemini-embedding-001",
            "mrl_vector_size": None,
        }
        self.assertEqual(embedding_signature(base), embedding_signature(dict(base)))
        self.assertNotEqual(
            embedding_signature(base),
            embedding_signature({**base, "mrl_vector_size": 768}),
        )

    def test_model_change_changes_signature(self) -> None:
        from logic.runtime import embedding_signature

        a = embedding_signature({
            "embedding_provider": "google", "embedding_model": "m-a", "mrl_vector_size": None,
        })
        b = embedding_signature({
            "embedding_provider": "google", "embedding_model": "m-b", "mrl_vector_size": None,
        })
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
