from __future__ import annotations

import unittest
from pathlib import Path


class RouterImportStyleTests(unittest.TestCase):
    """Routers must import the deps MODULE, never names out of it.

    `from sentient.api.deps import state_store` binds the value at import
    time, so a test patching deps.state_store would have no effect and the
    router would keep using the real store -- a test passing for the wrong
    reason. Spec section 7.1. import-linter cannot see this, so it is pinned
    here instead.
    """

    def test_no_router_imports_names_out_of_deps(self):
        routers = Path(__file__).resolve().parent.parent / "src" / "sentient" / "api" / "routers"
        offenders = [
            path.name
            for path in sorted(routers.glob("*.py"))
            if "from sentient.api.deps import" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [], f"routers binding deps names at import time: {offenders}")

    def test_every_router_is_registered(self):
        from sentient.api.app import app

        routers = Path(__file__).resolve().parent.parent / "src" / "sentient" / "api" / "routers"
        expected = {p.stem for p in routers.glob("*.py") if p.stem != "__init__"}
        registered = {
            getattr(r, "endpoint", None).__module__.rsplit(".", 1)[-1]
            for r in app.routes
            if getattr(r, "endpoint", None) is not None
        }
        self.assertTrue(
            expected.issubset(registered),
            f"routers on disk but not included in app.py: {expected - registered}",
        )


if __name__ == "__main__":
    unittest.main()
