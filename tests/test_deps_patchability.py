from __future__ import annotations

import unittest
from unittest.mock import patch


class DepsPatchabilityTests(unittest.TestCase):
    """Routers must import the deps MODULE, not names out of it.

    `from deps import state_store` binds at import time, so patching
    deps.state_store would leave the router using the real store while the
    test believed it had a fake -- a test passing for the wrong reason.
    Spec section 7.1.
    """

    def test_patching_deps_state_store_is_visible_to_a_router(self):
        from fastapi.testclient import TestClient

        from sentient.api import deps
        from sentient.api.app import app

        sentinel = object()
        with patch.object(deps, "state_store", sentinel):
            self.assertIs(deps.state_store, sentinel)
            # The app still constructs; patching does not break import graphs.
            TestClient(app)

    def test_deps_exposes_every_singleton(self):
        from sentient.api import deps

        for name in (
            "_settings",
            "state_store",
            "identity_cache",
            "runtime_cache",
            "object_registry",
            "session_locks",
        ):
            self.assertTrue(hasattr(deps, name), f"deps is missing {name}")


if __name__ == "__main__":
    unittest.main()
