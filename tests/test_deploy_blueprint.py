from __future__ import annotations

import unittest
from pathlib import Path

import yaml

# yaml arrives with langchain-core rather than being declared here. That is fine for
# a test and would not be fine for src/, where core/config.py is the only module
# allowed to read configuration at all.

_BLUEPRINT = Path(__file__).resolve().parents[1] / "render.yaml"


class BlueprintTests(unittest.TestCase):
    """`render.yaml` is the committed form of the deployment.

    Nothing else checks it. A wrong variable name here does not fail a build or
    raise at boot -- `core/config.py` reads environment variables with defaults, so
    a typo silently leaves the default in place and the service runs with settings
    nobody chose. These assertions are the only thing standing between that and
    production.
    """

    def setUp(self):
        self.blueprint = yaml.safe_load(_BLUEPRINT.read_text(encoding="utf-8"))
        self.service = self.blueprint["services"][0]
        self.declared = {var["key"] for var in self.service["envVars"]}

    def test_every_declared_variable_is_one_config_actually_reads(self):
        """The failure this prevents is silent.

        `LLM_MODEL` and `EMBEDDING_MODEL` are the plausible-looking names that do not
        exist; the real ones are MODEL_NAME and EMBEDDING_MODEL_NAME. Setting the
        wrong one in a dashboard produces a service that answers every request on the
        default model, with nothing in the logs to say so.
        """
        config_source = (
            Path(__file__).resolve().parents[1] / "src" / "sentient" / "core" / "config.py"
        ).read_text(encoding="utf-8")

        # PORT is Render's own contract, read by the Dockerfile CMD rather than by
        # config.py, so it is legitimately absent from that file.
        platform_owned = {"PORT"}

        unknown = sorted(
            key
            for key in self.declared - platform_owned
            if f'"{key}"' not in config_source and f"'{key}'" not in config_source
        )
        self.assertEqual(unknown, [], "declared in render.yaml but read nowhere in config.py")

    def test_the_auth_base_url_ships_whenever_the_jwks_url_does(self):
        """Issuer verification turns itself off when both are unset.

        `_resolve_neon_auth_issuer` falls back to NEON_AUTH_BASE_URL's origin when
        NEON_AUTH_ISSUER is unset, and returns None when neither is set. PyJWT's
        issuer check returns early on None, so authentication stays on while the
        `iss` claim stops being checked at all -- no error and no log line, and a
        token minted by a different Neon branch would verify. H2 fixed exactly this;
        omitting the variable here would reintroduce it on the deployed service only.
        """
        if "NEON_AUTH_JWKS_URL" in self.declared:
            self.assertIn("NEON_AUTH_BASE_URL", self.declared)

    def test_no_secret_carries_a_value_in_git(self):
        """Anything with a value is committed in plain text, so nothing sensitive
        may have one. `sync: false` is how Render is told to prompt instead."""
        sensitive = ("KEY", "SECRET", "TOKEN", "PASSWORD", "DATABASE_URL", "DSN")
        for var in self.service["envVars"]:
            if any(word in var["key"] for word in sensitive):
                self.assertNotIn(
                    "value",
                    var,
                    f"{var['key']} would be committed in plain text; use sync: false",
                )

    def test_the_health_check_points_at_readiness(self):
        """`/health` answers 200 with the database unreachable, so a platform health
        check wired to it keeps a broken instance in the load balancer."""
        self.assertEqual(self.service["healthCheckPath"], "/health/ready")

    def test_the_dockerfile_path_exists(self):
        dockerfile = _BLUEPRINT.parent / self.service["dockerfilePath"].lstrip("./")
        self.assertTrue(dockerfile.is_file(), f"{dockerfile} is not in the repository")

    def test_the_vector_backend_is_one_the_factory_knows(self):
        """A free instance has no disk, so a FAISS index written under data/ would
        not survive a restart. The value still has to be one the factory selects on."""
        backend = next(v for v in self.service["envVars"] if v["key"] == "VECTOR_BACKEND")
        self.assertIn(backend["value"], {"faiss", "qdrant"})


if __name__ == "__main__":
    unittest.main()
