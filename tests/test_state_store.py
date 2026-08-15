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


class FreshCloneStartupTests(unittest.IsolatedAsyncioTestCase):
    """data_dir is gitignored, so a fresh clone has no data/ at all. The store is
    built at api.py import time, before any lifespan handler could create it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    async def test_creates_missing_data_dir(self):
        missing = Path(self.tmp.name) / "data"
        self.assertFalse(missing.exists())

        store = SQLiteStateStore(str(missing / "state.db"))

        self.assertTrue((missing / "state.db").exists())
        user = await store.ensure_user(None)
        self.assertIsNotNone(user["id"])

    async def test_get_state_store_boots_without_data_dir(self):
        from sentient.core.config import load_rag_settings
        from logic.state import get_state_store

        data_dir = str(Path(self.tmp.name) / "nested" / "data")
        with patch.dict(os.environ, {"DATA_DIR": data_dir}, clear=False):
            os.environ.pop("DATABASE_URL", None)
            store = get_state_store(load_rag_settings())

        self.assertIsInstance(store, SQLiteStateStore)
        self.assertTrue(Path(data_dir, "state.db").exists())


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SQLiteStateStore(str(Path(self.tmp.name) / "s.db"))

    def tearDown(self):
        self.tmp.cleanup()

    async def test_delete_project_cascades_to_threads_and_documents(self):
        user = await self.store.ensure_user("A")
        project = await self.store.create_project(user["id"], "P")
        thread = await self.store.upsert_thread(project["id"], "sess-1")
        await self.store.add_message(thread["id"], "user", "hello")
        await self.store.register_document(project["id"], "lore.pdf", 3, "sig")

        self.assertTrue(await self.store.delete_project(user["id"], project["id"]))
        self.assertIsNone(await self.store.get_project(user["id"], project["id"]))
        self.assertEqual(await self.store.list_threads(project["id"]), [])
        self.assertEqual(await self.store.list_documents(project["id"]), [])
        self.assertEqual(await self.store.list_messages(thread["id"]), [])

    async def test_delete_project_also_drops_its_config(self):
        user = await self.store.ensure_user("A")
        project = await self.store.create_project(user["id"], "P")
        await self.store.upsert_project_config(project["id"], persona_prompt="voice")

        await self.store.delete_project(user["id"], project["id"])
        self.assertIsNone(await self.store.get_project_config(project["id"]))

    async def test_delete_project_refuses_another_users_project(self):
        a = await self.store.ensure_user("A")
        b = await self.store.ensure_user("B")
        project = await self.store.create_project(a["id"], "P")

        self.assertFalse(await self.store.delete_project(b["id"], project["id"]))
        self.assertIsNotNone(await self.store.get_project(a["id"], project["id"]))

    async def test_delete_unknown_project_is_false(self):
        user = await self.store.ensure_user("A")
        self.assertFalse(await self.store.delete_project(user["id"], "no-such-project"))

    async def test_rename_project(self):
        user = await self.store.ensure_user("A")
        project = await self.store.create_project(user["id"], "Old")

        renamed = await self.store.rename_project(user["id"], project["id"], "New")
        self.assertEqual(renamed["name"], "New")
        self.assertIsNone(await self.store.rename_project("nobody", project["id"], "Hax"))

    async def test_rename_leaves_another_users_project_untouched(self):
        a = await self.store.ensure_user("A")
        b = await self.store.ensure_user("B")
        project = await self.store.create_project(a["id"], "Original")

        self.assertIsNone(await self.store.rename_project(b["id"], project["id"], "Hax"))
        # Ownership is filtered in the UPDATE itself, not just in the row we return.
        still = await self.store.get_project(a["id"], project["id"])
        self.assertEqual(still["name"], "Original")

    async def test_delete_thread_cascades_to_messages(self):
        user = await self.store.ensure_user("A")
        project = await self.store.create_project(user["id"], "P")
        thread = await self.store.upsert_thread(project["id"], "sess-1")
        await self.store.add_message(thread["id"], "user", "hello")

        self.assertTrue(await self.store.delete_thread(user["id"], thread["id"]))
        self.assertIsNone(await self.store.get_thread(user["id"], thread["id"]))
        self.assertEqual(await self.store.list_messages(thread["id"]), [])

    async def test_delete_thread_refuses_another_users_thread(self):
        a = await self.store.ensure_user("A")
        b = await self.store.ensure_user("B")
        project = await self.store.create_project(a["id"], "P")
        thread = await self.store.upsert_thread(project["id"], "sess-1")

        self.assertFalse(await self.store.delete_thread(b["id"], thread["id"]))
        self.assertIsNotNone(await self.store.get_thread(a["id"], thread["id"]))

    async def test_delete_document(self):
        user = await self.store.ensure_user("A")
        project = await self.store.create_project(user["id"], "P")
        await self.store.register_document(project["id"], "lore.pdf", 3, "sig")

        self.assertTrue(await self.store.delete_document(project["id"], "lore.pdf"))
        self.assertEqual(await self.store.list_documents(project["id"]), [])
        self.assertFalse(await self.store.delete_document(project["id"], "lore.pdf"))

    async def test_delete_document_is_scoped_to_its_project(self):
        user = await self.store.ensure_user("A")
        mine = await self.store.create_project(user["id"], "Mine")
        other = await self.store.create_project(user["id"], "Other")
        await self.store.register_document(mine["id"], "lore.pdf", 3, "sig")

        # Same filename, different project: must not be collateral damage.
        self.assertFalse(await self.store.delete_document(other["id"], "lore.pdf"))
        self.assertEqual(len(await self.store.list_documents(mine["id"])), 1)


class PostgresStoreSurfaceTests(unittest.TestCase):
    """The asyncpg impl is only exercised for real at the V3 gate, so pin the one
    thing that is checkable offline: it implements every StateStore method the
    SQLite store does. Constructing it opens no connection (the pool is lazy)."""

    def test_satisfies_protocol(self):
        from logic.state.postgres_store import PostgresStateStore

        self.assertIsInstance(PostgresStateStore("postgres://user@host/db"), StateStore)

    def test_lifecycle_methods_mirror_the_sqlite_store(self):
        from logic.state.postgres_store import PostgresStateStore

        for name in (
            "delete_project", "rename_project", "delete_thread", "delete_document",
        ):
            self.assertTrue(
                callable(getattr(PostgresStateStore, name, None)),
                f"PostgresStateStore is missing {name}",
            )


class StateStoreFactoryTests(unittest.TestCase):
    def test_factory_uses_sqlite_by_default(self):
        from logic.state import get_state_store
        from logic.state.sqlite_store import SQLiteStateStore
        from sentient.core.config import load_rag_settings
        with patch.dict(os.environ, {"DATA_DIR": tempfile.mkdtemp()}, clear=True):
            store = get_state_store(load_rag_settings())
        self.assertIsInstance(store, SQLiteStateStore)

    def test_factory_uses_postgres_for_neon(self):
        from logic.state import get_state_store
        from logic.state.postgres_store import PostgresStateStore
        from sentient.core.config import load_rag_settings
        with patch.dict(os.environ, {"DATABASE_URL": "postgres://x", "DB_BACKEND": "neon"}, clear=True):
            store = get_state_store(load_rag_settings())
        self.assertIsInstance(store, PostgresStateStore)


if __name__ == "__main__":
    unittest.main()
