"""B2: `GET /v1/projects/{id}` — the read path the settings pane is built on.

Two PUTs existed with no GET, and `list_projects` is `SELECT * FROM projects`,
which never joins `project_configs`. H1 confirmed both live: Finding 3 measured
the 405, Finding 4 measured a project whose stored persona was NULL while the
NPC visibly had one from the preset fallback.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

import httpx
from langchain_core.embeddings import Embeddings


class FakeEmbeddings(Embeddings):
    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 1.0, 0.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


class ProjectReadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {"DATA_DIR": self.tmp.name, "VECTOR_BACKEND": "faiss"})
        self.env.start()
        self.addCleanup(self.env.stop)

        embeddings = patch(
            "sentient.adapters.documents.build_embeddings", return_value=FakeEmbeddings()
        )
        embeddings.start()
        self.addCleanup(embeddings.stop)

        from sentient.adapters.auth import IdentityCache
        from sentient.adapters.state import get_state_store
        from sentient.api import app as api
        from sentient.api import deps
        from sentient.core.cache import ObjectRegistry
        from sentient.core.config import load_rag_settings
        from sentient.services.runtime import RuntimeCache

        self.api = api
        self.deps = deps
        deps._settings = load_rag_settings()
        deps.state_store = get_state_store(deps._settings)
        deps.identity_cache = IdentityCache()
        deps.runtime_cache = RuntimeCache()
        deps.object_registry = ObjectRegistry()
        deps.get_default_archives.cache_clear()
        self.addCleanup(deps.get_default_archives.cache_clear)

        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://test"
        )
        self.addAsyncCleanup(self.client.aclose)

    async def _project(self, name: str = "Skyrim", base_preset: str | None = None) -> str:
        body: dict = {"name": name}
        if base_preset is not None:
            body["base_preset"] = base_preset
        response = await self.client.post("/v1/projects", json=body)
        self.assertEqual(response.status_code, 200)
        return response.json()["id"]

    async def test_a_fresh_project_reports_every_config_field_as_null(self):
        """`null` means unset, NOT "the default happens to be this". F3 has to tell
        those apart: rendering a resolved default into an input and saving it pins a
        value the user never chose, silently, on the first save."""
        project_id = await self._project("Skyrim", base_preset="skyrim")
        body = (await self.client.get(f"/v1/projects/{project_id}")).json()

        self.assertEqual(body["id"], project_id)
        self.assertEqual(body["name"], "Skyrim")
        self.assertEqual(body["base_preset"], "skyrim")

        config = body["config"]
        for field in ("llm_provider", "model_name", "temperature", "rag_top_k", "history_window"):
            self.assertIn(field, config)
            self.assertIsNone(config[field], f"{field} should be unset, not defaulted")

    async def test_written_values_come_back_and_unset_ones_stay_null(self):
        project_id = await self._project("Skyrim")
        await self.client.put(
            f"/v1/projects/{project_id}/config",
            json={"rag_top_k": 8, "temperature": 0.3},
        )
        config = (await self.client.get(f"/v1/projects/{project_id}")).json()["config"]

        self.assertEqual(config["rag_top_k"], 8)
        self.assertEqual(config["temperature"], 0.3)
        self.assertIsNone(config["rag_fetch_k"])

    async def test_the_persona_round_trips_and_reports_its_source(self):
        project_id = await self._project("Skyrim", base_preset="skyrim")

        first = (await self.client.get(f"/v1/projects/{project_id}")).json()
        self.assertEqual(first["persona_source"], "preset")
        self.assertTrue(first["persona_prompt"])

        await self.client.put(
            f"/v1/projects/{project_id}/persona",
            json={"system_prompt": "You are Lydia, housecarl of Whiterun."},
        )
        second = (await self.client.get(f"/v1/projects/{project_id}")).json()
        self.assertEqual(second["persona_source"], "custom")
        self.assertEqual(second["persona_prompt"], "You are Lydia, housecarl of Whiterun.")

    async def test_a_project_with_no_preset_reports_a_generic_persona(self):
        project_id = await self._project("Homebrew")
        body = (await self.client.get(f"/v1/projects/{project_id}")).json()

        self.assertEqual(body["persona_source"], "generic")
        self.assertEqual(body["persona_prompt"], "")

    async def test_the_reported_persona_is_the_one_the_npc_actually_speaks_with(self):
        """Finding 4 in reverse: the stored value and the effective value disagreed,
        so the editor has to report the effective one or it renders a blank field
        over a live persona and overwrites it on save."""
        from sentient.services.runtime import resolve_runtime_context

        project_id = await self._project("Skyrim", base_preset="skyrim")
        body = (await self.client.get(f"/v1/projects/{project_id}")).json()

        user = await self.deps.state_store.ensure_user(None)
        ctx = await resolve_runtime_context(
            self.deps.state_store,
            self.deps._settings,
            user_id=user["id"],
            user_key="_",
            project_id=project_id,
        )
        self.assertEqual(body["persona_prompt"], ctx.system_prompt)

    async def test_a_project_belonging_to_someone_else_is_404(self):
        stranger = await self.deps.state_store.ensure_user("stranger")
        theirs = await self.deps.state_store.create_project(stranger["id"], "Fallout")
        response = await self.client.get(f"/v1/projects/{theirs['id']}")
        self.assertEqual(response.status_code, 404)

    async def test_an_unknown_project_is_404(self):
        response = await self.client.get("/v1/projects/does-not-exist")
        self.assertEqual(response.status_code, 404)

    async def test_the_embedding_signature_is_exposed_for_the_reindex_warning(self):
        """F3 must warn before an embedding change triggers the reindex 409."""
        project_id = await self._project("Skyrim")
        body = (await self.client.get(f"/v1/projects/{project_id}")).json()
        self.assertIn("embedding_signature", body["config"])

    async def test_every_writable_config_column_is_readable(self):
        """A hand-maintained field list drifts the moment a knob is added, and the
        symptom is a settings pane that silently cannot see it."""
        from sentient.adapters.state.schema import _CONFIG_COLUMNS

        project_id = await self._project("Skyrim")
        config = (await self.client.get(f"/v1/projects/{project_id}")).json()["config"]

        expected = {c for c in _CONFIG_COLUMNS if c != "persona_prompt"}
        self.assertEqual(set(config), expected)


if __name__ == "__main__":
    unittest.main()
