from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sentient.core.config import load_rag_settings
from sentient.adapters.state.sqlite_store import SQLiteStateStore


class RuntimeContextTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SQLiteStateStore(str(Path(self.tmp.name) / "s.db"))
        self.settings = load_rag_settings()

    def tearDown(self):
        self.tmp.cleanup()

    async def test_no_project_matches_env_floor(self):
        from sentient.services.runtime import resolve_runtime_context
        ctx = await resolve_runtime_context(self.store, self.settings,
                                            user_id="u", user_key="default")
        self.assertEqual(ctx.llm_settings["model"], self.settings.llm_model)
        self.assertEqual(ctx.rag_settings["top_k"], self.settings.top_k)
        self.assertEqual(ctx.system_prompt, "")
        self.assertIsNone(ctx.project_id)

    async def test_project_config_overrides_floor(self):
        from sentient.services.runtime import resolve_runtime_context
        user = await self.store.ensure_user("A")
        proj = await self.store.create_project(user["id"], "Skyrim", base_preset="skyrim")
        await self.store.upsert_project_config(proj["id"], model_name="gemini-2.5-flash", rag_top_k=7)
        ctx = await resolve_runtime_context(self.store, self.settings, user_id=user["id"],
                                            user_key="uk", project_id=proj["id"])
        self.assertEqual(ctx.llm_settings["model"], "gemini-2.5-flash")   # overridden
        self.assertEqual(ctx.rag_settings["top_k"], 7)                    # overridden
        self.assertIn("Skyrim", ctx.system_prompt)                        # base_preset applied

    async def test_persona_prompt_beats_preset(self):
        from sentient.services.runtime import resolve_runtime_context
        user = await self.store.ensure_user("A")
        proj = await self.store.create_project(user["id"], "Skyrim", base_preset="skyrim")
        await self.store.upsert_project_config(
            proj["id"], persona_prompt="You are the voice of this world.")
        ctx = await resolve_runtime_context(self.store, self.settings, user_id=user["id"],
                                            user_key="uk", project_id=proj["id"])
        self.assertEqual(ctx.system_prompt, "You are the voice of this world.")

    async def test_signature_changes_with_model(self):
        from sentient.services.runtime import resolve_runtime_context
        user = await self.store.ensure_user("A")
        p1 = await self.store.create_project(user["id"], "P1")
        p2 = await self.store.create_project(user["id"], "P2")
        await self.store.upsert_project_config(p1["id"], model_name="model-a")
        await self.store.upsert_project_config(p2["id"], model_name="model-b")
        c1 = await resolve_runtime_context(self.store, self.settings, user_id=user["id"],
                                           user_key="uk", project_id=p1["id"])
        c2 = await resolve_runtime_context(self.store, self.settings, user_id=user["id"],
                                           user_key="uk", project_id=p2["id"])
        self.assertNotEqual(c1.config_signature, c2.config_signature)


class RuntimeCacheTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SQLiteStateStore(str(Path(self.tmp.name) / "s.db"))
        self.settings = load_rag_settings()

    def tearDown(self):
        self.tmp.cleanup()

    async def test_memoizes_and_invalidates(self):
        from sentient.services.runtime import RuntimeCache
        user = await self.store.ensure_user("A")
        proj = await self.store.create_project(user["id"], "P")
        await self.store.upsert_project_config(proj["id"], model_name="m1")
        cache = RuntimeCache()

        calls = {"n": 0}
        orig = self.store.get_project_config
        async def counting(pid):
            calls["n"] += 1
            return await orig(pid)
        self.store.get_project_config = counting  # type: ignore

        c1 = await cache.resolve(self.store, self.settings, user_id=user["id"], user_key="uk",
                                 project_id=proj["id"], session_id="s")
        c2 = await cache.resolve(self.store, self.settings, user_id=user["id"], user_key="uk",
                                 project_id=proj["id"], session_id="s2")
        self.assertEqual(c1.llm_settings["model"], "m1")
        self.assertEqual(c2.session_id, "s2")  # session id follows the call, not the cache
        self.assertEqual(calls["n"], 1)  # second served from cache

        await self.store.upsert_project_config(proj["id"], model_name="m2")
        cache.invalidate(proj["id"])
        c3 = await cache.resolve(self.store, self.settings, user_id=user["id"], user_key="uk",
                                 project_id=proj["id"], session_id="s")
        self.assertEqual(c3.llm_settings["model"], "m2")  # re-resolved after invalidation

    async def test_provider_key_is_part_of_cache_identity(self):
        from sentient.services.runtime import RuntimeCache

        cache = RuntimeCache()
        first = await cache.resolve(
            self.store,
            self.settings,
            user_id="default-user",
            user_key="default",
            project_id=None,
            provider_key="sk-provider-one",
        )
        second = await cache.resolve(
            self.store,
            self.settings,
            user_id="default-user",
            user_key="default",
            project_id=None,
            provider_key="sk-provider-two",
        )

        self.assertEqual(first.llm_settings["api_key"], "sk-provider-one")
        self.assertEqual(second.llm_settings["api_key"], "sk-provider-two")
        self.assertNotEqual(first.config_signature, second.config_signature)

    async def test_user_key_is_part_of_cache_identity(self):
        from sentient.services.runtime import RuntimeCache

        cache = RuntimeCache()
        first = await cache.resolve(
            self.store,
            self.settings,
            user_id="same-owner",
            user_key="key-a",
            project_id="same-project",
        )
        second = await cache.resolve(
            self.store,
            self.settings,
            user_id="same-owner",
            user_key="key-b",
            project_id="same-project",
        )

        self.assertEqual(first.user_key, "key-a")
        self.assertEqual(second.user_key, "key-b")


if __name__ == "__main__":
    unittest.main()
