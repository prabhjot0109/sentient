"""Pin the conftest scrub list against the configuration source.

`_CONFIG_ENV_VARS` in `tests/conftest.py` is what keeps a developer's real `.env`
out of the suite. It was hand-maintained and drifted: R1-R3 added
`NEON_AUTH_JWKS_URL` and `DATABASE_URL` without adding them there, so a populated
`.env` turned auth on for every test (18 failures, all 401) and pointed the state
store at live Neon. CI never saw it, because CI has no `.env`.

A list that must match another file by hand is a comment pretending to be code.
This test makes the match mechanical.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from tests.conftest import _CONFIG_ENV_VARS

_SRC = Path(__file__).resolve().parents[1] / "src" / "sentient"

# Modules whose env reads are configuration a stale .env could corrupt. Adapters
# that read a var only to pass it straight to a provider SDK are out of scope.
_CONFIG_MODULES = (
    _SRC / "core" / "config.py",
    _SRC / "adapters" / "state" / "__init__.py",
    _SRC / "api" / "app.py",
)

# Read at import time by the process that owns the value, not resolved per request.
_NOT_CONFIGURATION = frozenset({"PYTHON_DOTENV_DISABLED"})


def _env_names_read_by(path: Path) -> set[str]:
    """Every literal env var name the module reads, via os.getenv, os.environ or
    the _env_int/_env_float/_env_bool helpers."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func
            label = getattr(target, "attr", None) or getattr(target, "id", None)
            reads_env = label in ("getenv", "_env_int", "_env_float", "_env_bool")
            if reads_env and node.args and isinstance(node.args[0], ast.Constant):
                names.add(str(node.args[0].value))
        elif isinstance(node, ast.Subscript):
            value = node.value
            if getattr(value, "attr", None) == "environ" and isinstance(node.slice, ast.Constant):
                names.add(str(node.slice.value))

    return {name for name in names if name.isupper()} - _NOT_CONFIGURATION


class ConfigEnvScrubListTests(unittest.TestCase):
    def test_every_configuration_env_var_is_scrubbed(self):
        scrubbed = set(_CONFIG_ENV_VARS)
        for module in _CONFIG_MODULES:
            missing = _env_names_read_by(module) - scrubbed
            self.assertEqual(
                missing,
                set(),
                f"{module.name} reads env vars that tests/conftest.py does not scrub: "
                f"{sorted(missing)}. A populated .env would leak them into every test.",
            )

    def test_the_scrub_list_has_no_duplicates(self):
        self.assertEqual(len(_CONFIG_ENV_VARS), len(set(_CONFIG_ENV_VARS)))
