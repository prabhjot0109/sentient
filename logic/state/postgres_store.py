from __future__ import annotations

import asyncpg

from logic.state.sqlite_store import _CONFIG_COLUMNS, _DEFAULT_USER_SENTINEL


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
        # Apply the migration idempotently (create table if not exists ...).
        import pathlib
        sql = (pathlib.Path(__file__).resolve().parents[2]
               / "db" / "migrations" / "0001_runtime_schema.sql").read_text(encoding="utf-8")
        async with self._pool.acquire() as conn:  # type: ignore[union-attr]
            await conn.execute(sql)

    async def ensure_user(self, external_auth_id, email=None):
        key = external_auth_id if external_auth_id is not None else _DEFAULT_USER_SENTINEL
        pool = await self._pool_()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO users (external_auth_id, email) VALUES ($1,$2) "
                "ON CONFLICT (external_auth_id) DO UPDATE SET email=COALESCE(users.email, excluded.email) "
                "RETURNING id::text, external_auth_id, email", key, email)
        return dict(row)

    async def get_user_by_api_key_hash(self, key_hash):
        pool = await self._pool_()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT user_id::text AS user_id, revoked FROM api_keys WHERE key_hash=$1", key_hash)
        return dict(row) if row else None

    async def create_api_key(self, user_id, key_hash, label=None):
        pool = await self._pool_()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO api_keys (user_id, key_hash, label) VALUES ($1,$2,$3) "
                "RETURNING id::text, label, revoked", user_id, key_hash, label)
        return {**dict(row), "user_id": user_id}

    async def revoke_api_key(self, user_id, key_id):
        pool = await self._pool_()
        async with pool.acquire() as conn:
            res = await conn.execute("UPDATE api_keys SET revoked=true WHERE id=$1 AND user_id=$2",
                                     key_id, user_id)
        return res.endswith("1")

    async def list_api_keys(self, user_id):
        pool = await self._pool_()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id::text, label, revoked, created_at FROM api_keys WHERE user_id=$1", user_id)
        return [dict(r) for r in rows]

    async def create_project(self, user_id, name, base_preset="custom"):
        pool = await self._pool_()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "INSERT INTO projects (user_id, name, base_preset) VALUES ($1,$2,$3) "
                    "RETURNING id::text, name, base_preset, status", user_id, name, base_preset)
                await conn.execute("INSERT INTO project_configs (project_id) VALUES ($1)", row["id"])
        return {**dict(row), "user_id": user_id}

    async def get_project(self, user_id, project_id):
        pool = await self._pool_()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id::text, user_id::text, name, base_preset, status FROM projects "
                "WHERE id=$1 AND user_id=$2", project_id, user_id)
        return dict(row) if row else None

    async def list_projects(self, user_id):
        pool = await self._pool_()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id::text, name, base_preset, status FROM projects WHERE user_id=$1 "
                "ORDER BY created_at DESC", user_id)
        return [dict(r) for r in rows]

    async def set_project_status(self, project_id, status):
        pool = await self._pool_()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE projects SET status=$1 WHERE id=$2", status, project_id)

    async def get_project_config(self, project_id):
        pool = await self._pool_()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM project_configs WHERE project_id=$1", project_id)
        return dict(row) if row else None

    async def upsert_project_config(self, project_id, **fields):
        cols = [c for c in fields if c in _CONFIG_COLUMNS]
        pool = await self._pool_()
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO project_configs (project_id) VALUES ($1) "
                               "ON CONFLICT (project_id) DO NOTHING", project_id)
            if cols:
                sets = ", ".join(f"{c}=${i+2}" for i, c in enumerate(cols))
                await conn.execute(
                    f"UPDATE project_configs SET {sets}, updated_at=now() WHERE project_id=$1",
                    project_id, *[fields[c] for c in cols])
            row = await conn.fetchrow("SELECT * FROM project_configs WHERE project_id=$1", project_id)
        return dict(row)

    async def register_document(self, project_id, filename, chunk_count, embedding_signature, status="ready"):
        pool = await self._pool_()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO documents (project_id, filename, chunk_count, embedding_signature, status) "
                "VALUES ($1,$2,$3,$4,$5) ON CONFLICT (project_id, filename) DO UPDATE SET "
                "chunk_count=excluded.chunk_count, embedding_signature=excluded.embedding_signature, "
                "status=excluded.status, updated_at=now() "
                "RETURNING id::text, filename, chunk_count, embedding_signature, status",
                project_id, filename, chunk_count, embedding_signature, status)
        return {**dict(row), "project_id": project_id}

    async def set_document_status(self, project_id, filename, status):
        pool = await self._pool_()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE documents SET status=$1, updated_at=now() "
                               "WHERE project_id=$2 AND filename=$3", status, project_id, filename)

    async def list_documents(self, project_id):
        pool = await self._pool_()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM documents WHERE project_id=$1", project_id)
        return [dict(r) for r in rows]
