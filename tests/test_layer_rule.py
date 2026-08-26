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
        """A router file that nobody include_router()s is dead code that looks live.

        Walks nested routes rather than reading `app.routes` flat. FastAPI 0.141 /
        Starlette 1.x stopped flattening `include_router` into `app.routes` and now
        leaves an `_IncludedRouter` wrapper -- which exposes the real router as
        `original_router`, not as `routes` -- so the flat read found ZERO endpoints
        and this guard reported all nine routers missing while the app served all
        25 paths perfectly well. Both container attributes are followed, so this
        keeps working whichever shape a future version picks.
        """
        from sentient.api.app import app

        routers = Path(__file__).resolve().parent.parent / "src" / "sentient" / "api" / "routers"
        expected = {p.stem for p in routers.glob("*.py") if p.stem != "__init__"}

        def modules_of(routes) -> set[str]:
            found: set[str] = set()
            for route in routes:
                endpoint = getattr(route, "endpoint", None)
                if endpoint is not None:
                    found.add(endpoint.__module__.rsplit(".", 1)[-1])
                nested = getattr(route, "original_router", None)
                found |= modules_of(getattr(route, "routes", ()) or ())
                if nested is not None:
                    found |= modules_of(getattr(nested, "routes", ()) or ())
            return found

        registered = modules_of(app.routes)
        # Belt and braces: an empty `registered` would make issubset trivially
        # false and read as "nothing is wired", but a future shape change could
        # equally make it trivially TRUE against an empty `expected`.
        self.assertTrue(expected, "no router files found on disk")
        self.assertTrue(
            expected.issubset(registered),
            f"routers on disk but not included in app.py: {expected - registered}",
        )


if __name__ == "__main__":
    unittest.main()
