from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PackageInstallTests(unittest.TestCase):
    """The package must import without depending on the working directory.

    Before R9 the repo had no [build-system], so `import logic` only worked
    because the repo root happened to be sys.path[0]. Running from anywhere
    else broke it -- which is why run_rag.py carried a sys.path.append hack.
    """

    def test_sentient_imports_from_an_unrelated_working_directory(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            result = subprocess.run(
                [sys.executable, "-c", "import sentient; print(sentient.__name__)"],
                cwd=elsewhere,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "sentient")

    def test_package_declares_a_build_backend(self):
        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        text = pyproject.read_text(encoding="utf-8")
        self.assertIn("[build-system]", text)
        self.assertIn("build-backend", text)


if __name__ == "__main__":
    unittest.main()
