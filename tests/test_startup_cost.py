from __future__ import annotations

import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

# torch costs 158 MB of RSS and 7 s of cold start, and until 2026-08-31 every
# deployment paid both on every boot whether or not it used the one provider that
# needs it. Measured on a cold interpreter:
#
#   import sentient.api.app, torch present  ->  305 MB, 20.0 s
#   import sentient.api.app, torch absent   ->  147 MB,  3.3 s
#
# Two separate causes, and only fixing both moves the number. `adapters/documents.py`
# and `adapters/llm/models.py` imported `langchain_huggingface` at module scope for
# code inside `if provider == "huggingface"` branches. And `langchain_groq` imports
# `transformers` for token counting, which imports torch whenever torch is merely
# *installed* -- so deferring our own imports was not enough on its own, and the
# package had to leave the default dependency set too.
#
# No existing gate catches either one. The import-linter contract governs WHICH
# layer may import what, not WHEN, so ruff, mypy, import-linter and the rest of the
# suite all passed throughout.
#
# These tests block torch in a subprocess rather than asserting on `sys.modules`
# here. A developer machine has the `local-embeddings` group installed, so an
# in-process check would answer a question about this test session instead of about
# a cold start on the deployed image. Same reason `test_package_import.py` shells
# out.
_BLOCK_TORCH = """
import sys


class _Blocker:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in ("torch", "sentence_transformers"):
            raise ImportError(f"{name} is not installed on the deployed image")
        return None


sys.meta_path.insert(0, _Blocker())
"""

# The `observability` group is not in `default-groups`, so a fresh clone has
# neither package. A developer machine that ran `uv sync --group observability`
# does, which is exactly why this is blocked in a subprocess rather than asserted
# on `sys.modules`: the question is about the fresh clone, not this session.
_BLOCK_OBSERVABILITY = """
import sys


class _ObservabilityBlocker:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in ("sentry_sdk", "langfuse"):
            raise ImportError(f"{name} is in the optional observability group")
        return None


sys.meta_path.insert(0, _ObservabilityBlocker())
"""

_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _run(
    statement: str, *, block_torch: bool, block_observability: bool = False
) -> subprocess.CompletedProcess[str]:
    source = _BLOCK_TORCH if block_torch else ""
    source += (_BLOCK_OBSERVABILITY if block_observability else "") + statement
    return subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
    )


class TorchIsOptionalTests(unittest.TestCase):
    """The deployed image has no torch. The app must not need one."""

    def test_the_app_imports_with_torch_absent(self):
        result = _run("import sentient.api.app", block_torch=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_chat_model_adapter_imports_with_torch_absent(self):
        result = _run("import sentient.adapters.llm.models", block_torch=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_document_adapter_imports_with_torch_absent(self):
        result = _run("import sentient.adapters.documents", block_torch=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_hosted_embedding_provider_still_builds_with_torch_absent(self):
        """The path the deployment actually takes, not just the import.

        An import that succeeds while every provider construction fails would
        satisfy the three tests above and still be broken in production.
        """
        result = _run(
            "from sentient.adapters.documents import build_embeddings\n"
            "e = build_embeddings('google', 'models/embedding-001', None, 'test-key')\n"
            "print(type(e).__name__)",
            block_torch=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "GoogleGenerativeAIEmbeddings")

    def test_the_local_provider_explains_itself_with_torch_absent(self):
        """A missing optional group must name itself and both ways out.

        Left alone, this surfaces as sentence_transformers' own ImportError telling
        the operator to `pip install` into a uv-managed environment, which is the
        wrong instruction for this repo and says nothing about the alternative.
        """
        result = _run(
            "from sentient.adapters.documents import build_embeddings\n"
            "from sentient.core.errors import InvalidRequest\n"
            "try:\n"
            "    build_embeddings('huggingface', 'BAAI/bge-base-en-v1.5', None, None)\n"
            "except InvalidRequest as exc:\n"
            "    print(str(exc))\n",
            block_torch=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        message = result.stdout
        self.assertIn("local-embeddings", message)
        self.assertIn("EMBEDDING_PROVIDER", message)


class DependencyDeclarationTests(unittest.TestCase):
    def setUp(self):
        with _PYPROJECT.open("rb") as handle:
            self.pyproject = tomllib.load(handle)

    def _requirement_names(self, requirements: list[str]) -> set[str]:
        return {
            requirement.split(";")[0].split("[")[0].strip().split(" ")[0].rstrip("<>=!~0123456789.")
            for requirement in requirements
        }

    def test_sentence_transformers_is_not_a_default_dependency(self):
        names = self._requirement_names(self.pyproject["project"]["dependencies"])
        self.assertNotIn(
            "sentence-transformers",
            names,
            "it pulls torch, which is 158 MB the deployed image cannot spend; it "
            "belongs in the local-embeddings group",
        )

    def test_the_local_embeddings_group_exists(self):
        groups = self.pyproject["dependency-groups"]
        self.assertIn("local-embeddings", groups)
        self.assertIn("sentence-transformers", self._requirement_names(groups["local-embeddings"]))

    def test_a_fresh_clone_still_installs_it(self):
        """`uv sync` must keep behaving like main.

        CLAUDE.md makes "a fresh clone must behave like main" a hard constraint, and
        the huggingface embedding provider is what an unset EMBEDDING_PROVIDER falls
        back to. Listing the group in default-groups is what keeps `uv sync` whole
        while letting the image opt out with --no-default-groups.
        """
        self.assertIn(
            "local-embeddings",
            self.pyproject["tool"]["uv"]["default-groups"],
        )


class ObservabilityIsOptionalTests(unittest.TestCase):
    """Sentry and Langfuse must be absent from a fresh clone, and harmless when
    absent from a configured one. An observability tool that can stop the service
    booting is a new way for the product to fail, which is worse than not having
    it. Measured 2026-09-02 on the deployed image shape (torch blocked): importing
    the app costs 148.4 MB, and the two packages add 4.1 MB each on top -- 8.2 MB
    against a 512 MB budget the container currently uses 199 MB of.
    """

    def setUp(self):
        with _PYPROJECT.open("rb") as handle:
            self.pyproject = tomllib.load(handle)

    def test_the_observability_group_exists_and_holds_both(self):
        group = self.pyproject["dependency-groups"]["observability"]
        joined = " ".join(group)
        self.assertIn("sentry-sdk", joined)
        self.assertIn("langfuse", joined)

    def test_it_is_not_installed_by_a_fresh_clone(self):
        """Unlike `local-embeddings`, which is in `default-groups` so `uv sync`
        keeps behaving like main. Both integrations ship OFF, and installing them
        anyway would not make them optional -- only quiet."""
        self.assertNotIn(
            "observability",
            self.pyproject["tool"]["uv"]["default-groups"],
            "both integrations ship off; a fresh clone must not install them",
        )

    def test_the_app_imports_with_neither_package_installed(self):
        result = _run("import sentient.api.app", block_torch=True, block_observability=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_configured_dsn_with_no_sdk_warns_instead_of_raising(self):
        """The worst case for the operator: the DSN is set on a deployment whose
        image forgot `--group observability`. It must log and carry on, not die
        during the lifespan."""
        result = _run(
            "import os\n"
            "os.environ['SENTRY_DSN'] = 'https://k@example.test/1'\n"
            "from sentient.api.app import configure_error_tracking\n"
            "from sentient.core.config import load_rag_settings\n"
            "print(configure_error_tracking(load_rag_settings()))\n",
            block_torch=True,
            block_observability=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().splitlines()[-1], "False")


class ModuleScopeImportTests(unittest.TestCase):
    def test_the_app_does_not_import_langchain_huggingface_at_module_scope(self):
        """Ours to control, and true regardless of what is installed.

        The tests above would also pass if `langchain_huggingface` were imported
        eagerly but happened to be light. This one pins the discipline itself, so
        the next module-scope import is caught even on a machine with torch.
        """
        result = _run(
            "import sentient.api.app\nimport sys\nprint('langchain_huggingface' in sys.modules)",
            block_torch=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False")


if __name__ == "__main__":
    unittest.main()
