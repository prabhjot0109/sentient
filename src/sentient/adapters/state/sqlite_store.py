from __future__ import annotations

import asyncio
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sentient.adapters.state.schema import _CONFIG_COLUMNS, _DEFAULT_USER_SENTINEL


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SQLiteStateStore:
    """SQLite StateStore. Blocking sqlite3 calls are offloaded via asyncio.to_thread;
    one short-lived connection per op (no cross-thread handle sharing)."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init(self) -> None:
        # sqlite cannot create a database inside a directory that does not exist,
        # and data_dir is gitignored — a fresh clone has no data/ at all. This store
        # is constructed at api import time, before any lifespan handler could make
        # it, so the guard belongs here (as in SQLiteChatStore._ensure_storage).
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                  id TEXT PRIMARY KEY, external_auth_id TEXT UNIQUE, email TEXT, created_at TEXT);
                CREATE TABLE IF NOT EXISTS api_keys (
                  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, key_hash TEXT NOT NULL UNIQUE,
                  label TEXT, revoked INTEGER DEFAULT 0, created_at TEXT,
                  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS projects (
                  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL,
                  base_preset TEXT NOT NULL DEFAULT 'custom', status TEXT NOT NULL DEFAULT 'active',
                  created_at TEXT, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS project_configs (
                  project_id TEXT PRIMARY KEY, llm_provider TEXT, embedding_provider TEXT,
                  model_name TEXT, embedding_model_name TEXT, temperature REAL, max_tokens INTEGER,
                  mrl_vector_size INTEGER, reasoning_effort TEXT, reasoning_format TEXT,
                  rag_search_type TEXT, rag_top_k INTEGER, rag_fetch_k INTEGER, rag_mmr_lambda REAL,
                  rag_score_threshold REAL, rag_chunk_size INTEGER, rag_chunk_overlap INTEGER,
                  persona_prompt TEXT, history_window INTEGER,
                  embedding_signature TEXT, updated_at TEXT,
                  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS chat_threads (
                  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, npc_name TEXT,
                  session_id TEXT NOT NULL, title TEXT, prefix_hash TEXT,
                  created_at TEXT, updated_at TEXT,
                  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE);
                CREATE INDEX IF NOT EXISTS chat_threads_session_idx ON chat_threads(session_id);
                CREATE UNIQUE INDEX IF NOT EXISTS chat_threads_project_session_idx
                  ON chat_threads(project_id, session_id);
                CREATE TABLE IF NOT EXISTS provider_credentials (
                  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, provider TEXT NOT NULL,
                  encrypted_key TEXT NOT NULL, key_hint TEXT, created_at TEXT,
                  UNIQUE(user_id, provider),
                  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS chat_messages (
                  id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, role TEXT NOT NULL,
                  content TEXT NOT NULL, created_at TEXT,
                  model TEXT, prompt_tokens INTEGER, completion_tokens INTEGER,
                  total_tokens INTEGER,
                  FOREIGN KEY(thread_id) REFERENCES chat_threads(id) ON DELETE CASCADE);
                CREATE INDEX IF NOT EXISTS chat_messages_thread_idx
                  ON chat_messages(thread_id, created_at);
                CREATE TABLE IF NOT EXISTS documents (
                  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, filename TEXT NOT NULL,
                  chunk_count INTEGER DEFAULT 0, embedding_signature TEXT,
                  status TEXT NOT NULL DEFAULT 'processing', size_bytes INTEGER,
                  created_at TEXT, updated_at TEXT,
                  UNIQUE(project_id, filename),
                  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE);
                """
            )

            def _ensure_columns(table: str, columns: dict[str, str]) -> None:
                # sqlite has no `ADD COLUMN IF NOT EXISTS`, and CREATE TABLE IF NOT
                # EXISTS above is a no-op on a database that already has the table.
                # Existing data/state.db files therefore need this explicitly.
                existing = {
                    row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
                }
                for name, ddl_type in columns.items():
                    if name not in existing:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}")

            _ensure_columns("chat_threads", {"prefix_hash": "TEXT"})
            _ensure_columns(
                "chat_messages",
                {
                    "model": "TEXT",
                    "prompt_tokens": "INTEGER",
                    "completion_tokens": "INTEGER",
                    "total_tokens": "INTEGER",
                },
            )
            _ensure_columns("documents", {"size_bytes": "INTEGER"})
            # Indexed only here, after the column is guaranteed to exist: inside the
            # script above it would reference a column an older database lacks.
            conn.execute(
                "CREATE INDEX IF NOT EXISTS chat_threads_project_prefix_idx "
                "ON chat_threads(project_id, prefix_hash)"
            )

    # ---- users / api keys ----
    def _ensure_user(self, external_auth_id: str | None, email: str | None) -> dict[str, Any]:
        key = external_auth_id if external_auth_id is not None else _DEFAULT_USER_SENTINEL
        with closing(self._connect()) as conn, conn:
            row = conn.execute("SELECT * FROM users WHERE external_auth_id=?", (key,)).fetchone()
            if row:
                return dict(row)
            uid = uuid4().hex
            conn.execute(
                "INSERT INTO users (id, external_auth_id, email, created_at) VALUES (?,?,?,?)",
                (uid, key, email, _now()),
            )
            return {"id": uid, "external_auth_id": key, "email": email}

    async def ensure_user(
        self, external_auth_id: str | None, email: str | None = None
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._ensure_user, external_auth_id, email)

    def _get_user_by_api_key_hash(self, key_hash: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT user_id, revoked FROM api_keys WHERE key_hash=?", (key_hash,)
            ).fetchone()
        return {"user_id": row["user_id"], "revoked": bool(row["revoked"])} if row else None

    async def get_user_by_api_key_hash(self, key_hash: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_user_by_api_key_hash, key_hash)

    def _create_api_key(self, user_id: str, key_hash: str, label: str | None) -> dict[str, Any]:
        kid = uuid4().hex
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO api_keys (id, user_id, key_hash, label, revoked, created_at) "
                "VALUES (?,?,?,?,0,?)",
                (kid, user_id, key_hash, label, _now()),
            )
        return {"id": kid, "user_id": user_id, "label": label, "revoked": False}

    async def create_api_key(
        self, user_id: str, key_hash: str, label: str | None = None
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._create_api_key, user_id, key_hash, label)

    def _revoke_api_key(self, user_id: str, key_id: str) -> bool:
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                "UPDATE api_keys SET revoked=1 WHERE id=? AND user_id=?", (key_id, user_id)
            )
        return cur.rowcount > 0

    async def revoke_api_key(self, user_id: str, key_id: str) -> bool:
        return await asyncio.to_thread(self._revoke_api_key, user_id, key_id)

    def _list_api_keys(self, user_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT id, label, revoked, created_at FROM api_keys WHERE user_id=?", (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    async def list_api_keys(self, user_id: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_api_keys, user_id)

    # ---- projects ----
    def _create_project(self, user_id: str, name: str, base_preset: str) -> dict[str, Any]:
        pid = uuid4().hex
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO projects (id, user_id, name, base_preset, status, created_at) "
                "VALUES (?,?,?,?, 'active', ?)",
                (pid, user_id, name, base_preset, _now()),
            )
            conn.execute(
                "INSERT INTO project_configs (project_id, updated_at) VALUES (?,?)", (pid, _now())
            )
        return {
            "id": pid,
            "user_id": user_id,
            "name": name,
            "base_preset": base_preset,
            "status": "active",
        }

    async def create_project(
        self, user_id: str, name: str, base_preset: str = "custom"
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._create_project, user_id, name, base_preset)

    def _get_project(self, user_id: str, project_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, user_id)
            ).fetchone()
        return dict(row) if row else None

    async def get_project(self, user_id: str, project_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_project, user_id, project_id)

    def _list_projects(self, user_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM projects WHERE user_id=? ORDER BY created_at DESC", (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    async def list_projects(self, user_id: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_projects, user_id)

    def _set_project_status(self, project_id: str, status: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("UPDATE projects SET status=? WHERE id=?", (status, project_id))

    async def set_project_status(self, project_id: str, status: str) -> None:
        await asyncio.to_thread(self._set_project_status, project_id, status)

    def _delete_project(self, user_id: str, project_id: str) -> bool:
        # user_id is in the WHERE clause, not checked by the caller: a wrong owner
        # deletes nothing instead of someone else's project. Child rows go with it
        # through the ON DELETE CASCADE keys (PRAGMA foreign_keys is ON in _connect).
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute(
                "DELETE FROM projects WHERE id=? AND user_id=?", (project_id, user_id)
            )
        return cursor.rowcount > 0

    async def delete_project(self, user_id: str, project_id: str) -> bool:
        return await asyncio.to_thread(self._delete_project, user_id, project_id)

    def _rename_project(self, user_id: str, project_id: str, name: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE projects SET name=? WHERE id=? AND user_id=?",
                (name, project_id, user_id),
            )
            row = conn.execute(
                "SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, user_id)
            ).fetchone()
        return dict(row) if row else None

    async def rename_project(
        self, user_id: str, project_id: str, name: str
    ) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._rename_project, user_id, project_id, name)

    # ---- project_configs ----
    def _get_project_config(self, project_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM project_configs WHERE project_id=?", (project_id,)
            ).fetchone()
        return dict(row) if row else None

    async def get_project_config(self, project_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_project_config, project_id)

    def _upsert_project_config(self, project_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        cols = [c for c in fields if c in _CONFIG_COLUMNS]
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT OR IGNORE INTO project_configs (project_id, updated_at) VALUES (?,?)",
                (project_id, _now()),
            )
            if cols:
                assignments = ", ".join(f"{c}=?" for c in cols) + ", updated_at=?"
                values = [fields[c] for c in cols] + [_now(), project_id]
                conn.execute(f"UPDATE project_configs SET {assignments} WHERE project_id=?", values)
            row = conn.execute(
                "SELECT * FROM project_configs WHERE project_id=?", (project_id,)
            ).fetchone()
        return dict(row)

    async def upsert_project_config(self, project_id: str, **fields: Any) -> dict[str, Any]:
        return await asyncio.to_thread(self._upsert_project_config, project_id, fields)

    # ---- documents ----
    def _register_document(
        self,
        project_id: str,
        filename: str,
        chunk_count: int,
        embedding_signature: str,
        status: str,
        size_bytes: int | None,
    ) -> dict[str, Any]:
        did = uuid4().hex
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO documents (id, project_id, filename, chunk_count, embedding_signature, "
                "status, size_bytes, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(project_id, filename) DO UPDATE SET chunk_count=excluded.chunk_count, "
                "embedding_signature=excluded.embedding_signature, status=excluded.status, "
                # A re-register that reports no size keeps the size already on the row:
                # the status flip from processing to ready carries no byte count, and
                # nulling it there would silently drop the row out of the quota sum.
                "size_bytes=COALESCE(excluded.size_bytes, documents.size_bytes), "
                "updated_at=excluded.updated_at",
                (
                    did,
                    project_id,
                    filename,
                    chunk_count,
                    embedding_signature,
                    status,
                    size_bytes,
                    _now(),
                    _now(),
                ),
            )
            row = conn.execute(
                "SELECT * FROM documents WHERE project_id=? AND filename=?", (project_id, filename)
            ).fetchone()
        return dict(row)

    async def register_document(
        self,
        project_id: str,
        filename: str,
        chunk_count: int,
        embedding_signature: str,
        status: str = "ready",
        *,
        size_bytes: int | None = None,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._register_document,
            project_id,
            filename,
            chunk_count,
            embedding_signature,
            status,
            size_bytes,
        )

    def _set_document_status(self, project_id: str, filename: str, status: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE documents SET status=?, updated_at=? WHERE project_id=? AND filename=?",
                (status, _now(), project_id, filename),
            )

    async def set_document_status(self, project_id: str, filename: str, status: str) -> None:
        await asyncio.to_thread(self._set_document_status, project_id, filename, status)

    def _list_documents(self, project_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE project_id=?", (project_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def _delete_document(self, project_id: str, filename: str) -> bool:
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute(
                "DELETE FROM documents WHERE project_id=? AND filename=?",
                (project_id, filename),
            )
        return cursor.rowcount > 0

    async def delete_document(self, project_id: str, filename: str) -> bool:
        return await asyncio.to_thread(self._delete_document, project_id, filename)

    async def list_documents(self, project_id: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_documents, project_id)

    # ---- provider credentials ----
    def _upsert_credential(
        self, user_id: str, provider: str, encrypted_key: str, hint: str
    ) -> dict[str, Any]:
        credential_id = uuid4().hex
        created_at = _now()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO provider_credentials (id, user_id, provider, encrypted_key, key_hint, created_at) "
                "VALUES (?,?,?,?,?,?) ON CONFLICT(user_id, provider) DO UPDATE SET "
                "encrypted_key=excluded.encrypted_key, key_hint=excluded.key_hint, created_at=excluded.created_at",
                (credential_id, user_id, provider, encrypted_key, hint, created_at),
            )
            row = conn.execute(
                "SELECT id, user_id, provider, encrypted_key, key_hint, created_at "
                "FROM provider_credentials WHERE user_id=? AND provider=?",
                (user_id, provider),
            ).fetchone()
        return dict(row)

    async def upsert_credential(
        self, user_id: str, provider: str, encrypted_key: str, key_hint: str
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._upsert_credential, user_id, provider, encrypted_key, key_hint
        )

    def _get_credential(self, user_id: str, provider: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT id, user_id, provider, encrypted_key, key_hint, created_at "
                "FROM provider_credentials WHERE user_id=? AND provider=?",
                (user_id, provider),
            ).fetchone()
        return dict(row) if row else None

    async def get_credential(self, user_id: str, provider: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_credential, user_id, provider)

    def _list_credentials(self, user_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT provider, key_hint, created_at FROM provider_credentials "
                "WHERE user_id=? ORDER BY provider",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    async def list_credentials(self, user_id: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_credentials, user_id)

    def _delete_credential(self, user_id: str, provider: str) -> bool:
        with closing(self._connect()) as conn, conn:
            result = conn.execute(
                "DELETE FROM provider_credentials WHERE user_id=? AND provider=?",
                (user_id, provider),
            )
        return result.rowcount > 0

    async def delete_credential(self, user_id: str, provider: str) -> bool:
        return await asyncio.to_thread(self._delete_credential, user_id, provider)

    # ---- threads / messages ----
    def _upsert_thread(
        self, project_id: str, session_id: str, npc_name: str | None, title: str | None
    ) -> dict[str, Any]:
        thread_id = uuid4().hex
        now = _now()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO chat_threads (id, project_id, npc_name, session_id, title, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?) ON CONFLICT(project_id, session_id) DO UPDATE SET "
                "npc_name=COALESCE(excluded.npc_name, chat_threads.npc_name), "
                "title=COALESCE(excluded.title, chat_threads.title), updated_at=excluded.updated_at",
                (thread_id, project_id, npc_name, session_id, title, now, now),
            )
            row = conn.execute(
                "SELECT * FROM chat_threads WHERE project_id=? AND session_id=?",
                (project_id, session_id),
            ).fetchone()
        return dict(row)

    async def upsert_thread(
        self,
        project_id: str,
        session_id: str,
        *,
        npc_name: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._upsert_thread, project_id, session_id, npc_name, title)

    def _get_thread(self, user_id: str, thread_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT t.* FROM chat_threads t JOIN projects p ON p.id=t.project_id "
                "WHERE t.id=? AND p.user_id=?",
                (thread_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    async def get_thread(self, user_id: str, thread_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_thread, user_id, thread_id)

    def _get_thread_by_prefix(self, project_id: str, prefix_hash: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM chat_threads WHERE project_id=? AND prefix_hash=? "
                "ORDER BY updated_at DESC LIMIT 1",
                (project_id, prefix_hash),
            ).fetchone()
        return dict(row) if row else None

    async def get_thread_by_prefix(
        self, project_id: str, prefix_hash: str
    ) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_thread_by_prefix, project_id, prefix_hash)

    def _set_thread_prefix(self, thread_id: str, prefix_hash: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE chat_threads SET prefix_hash=? WHERE id=?", (prefix_hash, thread_id)
            )

    async def set_thread_prefix(self, thread_id: str, prefix_hash: str) -> None:
        await asyncio.to_thread(self._set_thread_prefix, thread_id, prefix_hash)

    def _delete_thread(self, user_id: str, thread_id: str) -> bool:
        with closing(self._connect()) as conn, conn:
            # Ownership rides through the thread's project; a thread has no user_id.
            cursor = conn.execute(
                "DELETE FROM chat_threads WHERE id=? AND project_id IN "
                "(SELECT id FROM projects WHERE user_id=?)",
                (thread_id, user_id),
            )
        return cursor.rowcount > 0

    async def delete_thread(self, user_id: str, thread_id: str) -> bool:
        return await asyncio.to_thread(self._delete_thread, user_id, thread_id)

    def _add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        model: str | None,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        total_tokens: int | None,
    ) -> dict[str, Any]:
        message_id = uuid4().hex
        now = _now()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO chat_messages "
                "(id, thread_id, role, content, created_at, model, prompt_tokens, "
                " completion_tokens, total_tokens) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    message_id,
                    thread_id,
                    role,
                    content,
                    now,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                ),
            )
            conn.execute("UPDATE chat_threads SET updated_at=? WHERE id=?", (now, thread_id))
        return {
            "id": message_id,
            "thread_id": thread_id,
            "role": role,
            "content": content,
            "created_at": now,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

    async def add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        *,
        model: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._add_message,
            thread_id,
            role,
            content,
            model,
            prompt_tokens,
            completion_tokens,
            total_tokens,
        )

    def _list_threads(self, project_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM chat_threads WHERE project_id=? ORDER BY updated_at DESC, id DESC",
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    async def list_threads(self, project_id: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_threads, project_id)

    def _list_messages(self, thread_id: str, limit: int) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            # rowid is insertion order and the only stable tiebreak when two messages
            # land on the same timestamp; it has to key BOTH sorts, or the newest-first
            # window and the chronological re-sort disagree and the turn order inverts.
            rows = conn.execute(
                "SELECT id, thread_id, role, content, created_at, model, prompt_tokens, "
                "completion_tokens, total_tokens FROM "
                "(SELECT rowid AS seq, id, thread_id, role, content, created_at, model, "
                "prompt_tokens, completion_tokens, total_tokens FROM chat_messages "
                "WHERE thread_id=? ORDER BY created_at DESC, seq DESC LIMIT ?) "
                "ORDER BY created_at ASC, seq ASC",
                (thread_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    async def list_messages(self, thread_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_messages, thread_id, limit)
