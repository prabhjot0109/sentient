from __future__ import annotations

import unittest


class DomainErrorTests(unittest.TestCase):
    """core/ is the bottom layer and must know nothing about HTTP.

    Services raise these; routers translate them to HTTPException. If a
    status_code ever appears here, the layer rule has been breached in the
    one place no tool checks for it.
    """

    def test_every_error_descends_from_sentient_error(self):
        from sentient.core import errors

        for name in (
            "NotFound",
            "NotOwned",
            "Unauthenticated",
            "InvalidRequest",
            "ReindexInProgress",
            "QueueFull",
            "VaultUnavailable",
            "UpstreamFailure",
        ):
            cls = getattr(errors, name, None)
            self.assertIsNotNone(cls, f"errors.{name} is missing")
            self.assertTrue(issubclass(cls, errors.SentientError))

    def test_errors_carry_no_http_vocabulary(self):
        import inspect

        from sentient.core import errors

        source = inspect.getsource(errors)
        for forbidden in ("status_code", "HTTPException", "fastapi", "starlette"):
            self.assertNotIn(forbidden, source, f"core/errors.py leaks HTTP: {forbidden}")

    def test_not_found_and_not_owned_are_distinguishable(self):
        """Ownership failures return 404 on management routes and 403 on the
        completions route. R9 preserves both, so the types must not collapse."""
        from sentient.core import errors

        self.assertFalse(issubclass(errors.NotOwned, errors.NotFound))
        self.assertFalse(issubclass(errors.NotFound, errors.NotOwned))


if __name__ == "__main__":
    unittest.main()
