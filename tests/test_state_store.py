from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from logic.state.base import StateStore
from logic.state.sqlite_store import SQLiteStateStore


class SQLiteStateStoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SQLiteStateStore(str(Path(self.tmp.name) / "state.db"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_satisfies_protocol(self):
        self.assertIsInstance(self.store, StateStore)

    async def test_user_and_api_key_roundtrip(self):
        user = await self.store.ensure_user("auth-sub-1", "a@x.com")
        h = hashlib.sha256(b"raw-key").hexdigest()
        await self.store.create_api_key(user["id"], h, label="mantella")
        found = await self.store.get_user_by_api_key_hash(h)
        self.assertEqual(found["user_id"], user["id"])
        self.assertFalse(found["revoked"])
        self.assertIsNone(await self.store.get_user_by_api_key_hash("nope"))

    async def test_default_user_is_stable(self):
        u1 = await self.store.ensure_user(None)
        u2 = await self.store.ensure_user(None)
        self.assertEqual(u1["id"], u2["id"])  # one default row, not two

    async def test_project_ownership_isolation(self):
        a = await self.store.ensure_user("A")
        b = await self.store.ensure_user("B")
        proj = await self.store.create_project(a["id"], "Skyrim Live", base_preset="skyrim")
        self.assertIsNotNone(await self.store.get_project(a["id"], proj["id"]))
        self.assertIsNone(await self.store.get_project(b["id"], proj["id"]))  # B can't see A's project

    async def test_project_config_overlay_fields(self):
        u = await self.store.ensure_user("A")
        p = await self.store.create_project(u["id"], "P")
        await self.store.upsert_project_config(p["id"], model_name="gemini-2.5-flash", rag_top_k=6)
        cfg = await self.store.get_project_config(p["id"])
        self.assertEqual(cfg["model_name"], "gemini-2.5-flash")
        self.assertEqual(cfg["rag_top_k"], 6)

    async def test_persona_prompt_is_editable_config(self):
        u = await self.store.ensure_user("A")
        p = await self.store.create_project(u["id"], "P")
        await self.store.upsert_project_config(p["id"], persona_prompt="You are the world of Skyrim.")
        await self.store.upsert_project_config(p["id"], persona_prompt="v2 voice")
        cfg = await self.store.get_project_config(p["id"])
        self.assertEqual(cfg["persona_prompt"], "v2 voice")   # single editable persona per project

    async def test_document_registry_and_status(self):
        u = await self.store.ensure_user("A")
        p = await self.store.create_project(u["id"], "P")
        await self.store.register_document(p["id"], "lore.pdf", 42, "sig-abc")
        await self.store.set_document_status(p["id"], "lore.pdf", "reindexing")
        docs = await self.store.list_documents(p["id"])
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["status"], "reindexing")


class StateStoreFactoryTests(unittest.TestCase):
    def test_factory_uses_sqlite_by_default(self):
        from logic.state import get_state_store
        from logic.state.sqlite_store import SQLiteStateStore
        from logic.config import load_rag_settings
        with patch.dict(os.environ, {"DATA_DIR": tempfile.mkdtemp()}, clear=True):
            store = get_state_store(load_rag_settings())
        self.assertIsInstance(store, SQLiteStateStore)

    def test_factory_uses_postgres_for_neon(self):
        from logic.state import get_state_store
        from logic.state.postgres_store import PostgresStateStore
        from logic.config import load_rag_settings
        with patch.dict(os.environ, {"DATABASE_URL": "postgres://x", "DB_BACKEND": "neon"}, clear=True):
            store = get_state_store(load_rag_settings())
        self.assertIsInstance(store, PostgresStateStore)


if __name__ == "__main__":
    unittest.main()
