from __future__ import annotations

from typing import Any

import asyncpg

from sentient.adapters.state.schema import _CONFIG_COLUMNS, _DEFAULT_USER_SENTINEL


class PostgresStateStore:
    """asyncpg StateStore for Neon AND Supabase (both are Postgres; only the DSN differs).
    The pool is opened lazily so importing/constructing this never requires a live DB."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def _pool_(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=10)
            await self._ensure_schema()
        return self._pool

    async def _ensure_schema(self) -> None:
        # Migrations are idempotent DDL and must run in order for new deployments.
        # parents[4] is the repo root: this file sits at
        # <root>/src/sentient/adapters/state/postgres_store.py. Re-derive this
        # count if the module ever moves -- a wrong depth makes the glob return
        # an empty list, so migrations silently do not run and the first query
        # fails with "relation does not exist" instead of a path error.
        import pathlib

        migrations = sorted(
            (pathlib.Path(__file__).resolve().parents[4] / "migrations").glob("*.sql")
        )
        async with self._pool.acquire() as conn:  # type: ignore[union-attr]
            for migration in migrations:
                await conn.execute(migration.read_text(encoding="utf-8"))

    async def ensure_user(
        self, external_auth_id: str | None, email: str | None = None
    ) -> dict[str, Any]:
        key = external_auth_id if external_auth_id is not None else _DEFAULT_USER_SENTINEL
        pool = await self._pool_()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO users (external_auth_id, email) VALUES ($1,$2) "
                "ON CONFLICT (external_auth_id) DO UPDATE SET email=COALESCE(users.email, excluded.email) "
                "RETURNING id::text, external_auth_id, email",
                key,
                email,
            )
        return dict(row)

    async def get_user_by_api_key_hash(self, key_hash: str) -> dict[str, Any] | None:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT user_id::text AS user_id, revoked FROM api_keys WHERE key_hash=$1", key_hash
            )
        return dict(row) if row else None

    async def create_api_key(
        self, user_id: str, key_hash: str, label: str | None = None
    ) -> dict[str, Any]:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO api_keys (user_id, key_hash, label) VALUES ($1,$2,$3) "
                "RETURNING id::text, label, revoked",
                user_id,
                key_hash,
                label,
            )
        return {**dict(row), "user_id": user_id}

    async def revoke_api_key(self, user_id: str, key_id: str) -> bool:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            # asyncpg types execute() as Any; it returns the command status tag.
            res: str = await conn.execute(
                "UPDATE api_keys SET revoked=true WHERE id=$1 AND user_id=$2", key_id, user_id
            )
        return res.endswith("1")

    async def list_api_keys(self, user_id: str) -> list[dict[str, Any]]:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id::text, label, revoked, created_at FROM api_keys WHERE user_id=$1",
                user_id,
            )
        return [dict(r) for r in rows]

    async def create_project(
        self, user_id: str, name: str, base_preset: str = "custom"
    ) -> dict[str, Any]:
        pool = await self._pool_()
        async with pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "INSERT INTO projects (user_id, name, base_preset) VALUES ($1,$2,$3) "
                "RETURNING id::text, name, base_preset, status",
                user_id,
                name,
                base_preset,
            )
            await conn.execute("INSERT INTO project_configs (project_id) VALUES ($1)", row["id"])
        return {**dict(row), "user_id": user_id}

    async def get_project(self, user_id: str, project_id: str) -> dict[str, Any] | None:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id::text, user_id::text, name, base_preset, status FROM projects "
                "WHERE id=$1 AND user_id=$2",
                project_id,
                user_id,
            )
        return dict(row) if row else None

    async def list_projects(self, user_id: str) -> list[dict[str, Any]]:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id::text, name, base_preset, status FROM projects WHERE user_id=$1 "
                "ORDER BY created_at DESC",
                user_id,
            )
        return [dict(r) for r in rows]

    async def set_project_status(self, project_id: str, status: str) -> None:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE projects SET status=$1 WHERE id=$2", status, project_id)

    async def delete_project(self, user_id: str, project_id: str) -> bool:
        # user_id is filtered in the statement, so a wrong owner deletes nothing.
        # Configs, threads, messages and documents go with it via ON DELETE CASCADE.
        pool = await self._pool_()
        async with pool.acquire() as conn:
            # asyncpg types execute() as Any; it returns the command status tag.
            res: str = await conn.execute(
                "DELETE FROM projects WHERE id=$1 AND user_id=$2", project_id, user_id
            )
        return res.endswith(" 1")

    async def rename_project(
        self, user_id: str, project_id: str, name: str
    ) -> dict[str, Any] | None:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE projects SET name=$3 WHERE id=$1 AND user_id=$2 "
                "RETURNING id::text, user_id::text, name, base_preset, status",
                project_id,
                user_id,
                name,
            )
        return dict(row) if row else None

    async def get_project_config(self, project_id: str) -> dict[str, Any] | None:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM project_configs WHERE project_id=$1", project_id
            )
        return dict(row) if row else None

    async def upsert_project_config(self, project_id: str, **fields: Any) -> dict[str, Any]:
        cols = [c for c in fields if c in _CONFIG_COLUMNS]
        pool = await self._pool_()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO project_configs (project_id) VALUES ($1) "
                "ON CONFLICT (project_id) DO NOTHING",
                project_id,
            )
            if cols:
                sets = ", ".join(f"{c}=${i + 2}" for i, c in enumerate(cols))
                await conn.execute(
                    f"UPDATE project_configs SET {sets}, updated_at=now() WHERE project_id=$1",
                    project_id,
                    *[fields[c] for c in cols],
                )
            row = await conn.fetchrow(
                "SELECT * FROM project_configs WHERE project_id=$1", project_id
            )
        return dict(row)

    async def register_document(
        self,
        project_id: str,
        filename: str,
        chunk_count: int,
        embedding_signature: str,
        status: str = "ready",
    ) -> dict[str, Any]:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO documents (project_id, filename, chunk_count, embedding_signature, status) "
                "VALUES ($1,$2,$3,$4,$5) ON CONFLICT (project_id, filename) DO UPDATE SET "
                "chunk_count=excluded.chunk_count, embedding_signature=excluded.embedding_signature, "
                "status=excluded.status, updated_at=now() "
                "RETURNING id::text, filename, chunk_count, embedding_signature, status",
                project_id,
                filename,
                chunk_count,
                embedding_signature,
                status,
            )
        return {**dict(row), "project_id": project_id}

    async def set_document_status(self, project_id: str, filename: str, status: str) -> None:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE documents SET status=$1, updated_at=now() "
                "WHERE project_id=$2 AND filename=$3",
                status,
                project_id,
                filename,
            )

    async def list_documents(self, project_id: str) -> list[dict[str, Any]]:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM documents WHERE project_id=$1", project_id)
        return [dict(r) for r in rows]

    async def delete_document(self, project_id: str, filename: str) -> bool:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            # asyncpg types execute() as Any; it returns the command status tag.
            res: str = await conn.execute(
                "DELETE FROM documents WHERE project_id=$1 AND filename=$2", project_id, filename
            )
        return res.endswith(" 1")

    async def upsert_credential(
        self, user_id: str, provider: str, encrypted_key: str, key_hint: str
    ) -> dict[str, Any]:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO provider_credentials (user_id, provider, encrypted_key, key_hint) "
                "VALUES ($1,$2,$3,$4) ON CONFLICT (user_id, provider) DO UPDATE SET "
                "encrypted_key=excluded.encrypted_key, key_hint=excluded.key_hint, created_at=now() "
                "RETURNING id::text, user_id::text, provider, encrypted_key, key_hint, created_at",
                user_id,
                provider,
                encrypted_key,
                key_hint,
            )
        return dict(row)

    async def get_credential(self, user_id: str, provider: str) -> dict[str, Any] | None:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id::text, user_id::text, provider, encrypted_key, key_hint, created_at "
                "FROM provider_credentials WHERE user_id=$1 AND provider=$2",
                user_id,
                provider,
            )
        return dict(row) if row else None

    async def list_credentials(self, user_id: str) -> list[dict[str, Any]]:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT provider, key_hint, created_at FROM provider_credentials "
                "WHERE user_id=$1 ORDER BY provider",
                user_id,
            )
        return [dict(row) for row in rows]

    async def delete_credential(self, user_id: str, provider: str) -> bool:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            # asyncpg types execute() as Any; it returns the command status tag.
            result: str = await conn.execute(
                "DELETE FROM provider_credentials WHERE user_id=$1 AND provider=$2",
                user_id,
                provider,
            )
        return result.endswith("1")

    async def upsert_thread(
        self,
        project_id: str,
        session_id: str,
        *,
        npc_name: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO chat_threads (project_id, npc_name, session_id, title) VALUES ($1,$2,$3,$4) "
                "ON CONFLICT (project_id, session_id) DO UPDATE SET "
                "npc_name=COALESCE(excluded.npc_name, chat_threads.npc_name), "
                "title=COALESCE(excluded.title, chat_threads.title), updated_at=now() "
                "RETURNING id::text, project_id::text, npc_name, session_id, title, created_at, updated_at",
                project_id,
                npc_name,
                session_id,
                title,
            )
        return dict(row)

    async def get_thread(self, user_id: str, thread_id: str) -> dict[str, Any] | None:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT t.id::text, t.project_id::text, t.npc_name, t.session_id, t.title, "
                "t.created_at, t.updated_at FROM chat_threads t JOIN projects p ON p.id=t.project_id "
                "WHERE t.id=$1 AND p.user_id=$2",
                thread_id,
                user_id,
            )
        return dict(row) if row else None

    async def delete_thread(self, user_id: str, thread_id: str) -> bool:
        # Ownership rides through the thread's project; a thread has no user_id.
        # Messages go with it via ON DELETE CASCADE.
        pool = await self._pool_()
        async with pool.acquire() as conn:
            # asyncpg types execute() as Any; it returns the command status tag.
            res: str = await conn.execute(
                "DELETE FROM chat_threads WHERE id=$1 AND project_id IN "
                "(SELECT id FROM projects WHERE user_id=$2)",
                thread_id,
                user_id,
            )
        return res.endswith(" 1")

    async def add_message(self, thread_id: str, role: str, content: str) -> dict[str, Any]:
        pool = await self._pool_()
        async with pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "INSERT INTO chat_messages (thread_id, role, content) VALUES ($1,$2,$3) "
                "RETURNING id::text, thread_id::text, role, content, created_at",
                thread_id,
                role,
                content,
            )
            await conn.execute("UPDATE chat_threads SET updated_at=now() WHERE id=$1", thread_id)
        return dict(row)

    async def list_threads(self, project_id: str) -> list[dict[str, Any]]:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id::text, project_id::text, npc_name, session_id, title, created_at, updated_at "
                "FROM chat_threads WHERE project_id=$1 ORDER BY updated_at DESC, id DESC",
                project_id,
            )
        return [dict(row) for row in rows]

    async def list_messages(self, thread_id: str, limit: int = 50) -> list[dict[str, Any]]:
        pool = await self._pool_()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id::text, thread_id::text, role, content, created_at FROM "
                "(SELECT id, thread_id, role, content, created_at FROM chat_messages WHERE thread_id=$1 "
                "ORDER BY created_at DESC, id DESC LIMIT $2) tail ORDER BY created_at, id",
                thread_id,
                limit,
            )
        return [dict(row) for row in rows]
