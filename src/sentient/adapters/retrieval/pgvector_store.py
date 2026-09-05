"""Pgvector-backed tenant retrieval, stored beside relational state.

The existing VectorBackend protocol has synchronous inspection/reclamation
methods (`exists`, `metadata`, `reset`, `clear_project`). `asyncpg` would make
those methods either lie or block an event loop, so this adapter uses psycopg's
synchronous connection and sends its heavier public operations through
``asyncio.to_thread``. FastAPI already runs the two synchronous health methods
in a worker thread, and project reclamation moves its call there too.
"""

from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Callable
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from sentient.core.config import RAGSettings

_TABLE = "sentient_vectors"

_SCHEMA = (
    "CREATE EXTENSION IF NOT EXISTS vector",
    """
    CREATE TABLE IF NOT EXISTS sentient_vectors (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      user_key text NOT NULL,
      project_id uuid,
      embedding_signature text,
      source text NOT NULL,
      content text NOT NULL,
      metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
      embedding vector NOT NULL,
      dimensions integer NOT NULL CHECK (dimensions > 0),
      created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS sentient_vectors_scope_idx
    ON sentient_vectors (user_key, project_id, embedding_signature)
    """,
    "CREATE INDEX IF NOT EXISTS sentient_vectors_source_idx ON sentient_vectors (source)",
)


def _vector_literal(vector: list[float]) -> str:
    """The text literal pgvector accepts without a Python-specific adapter.

    `psycopg` binds parameters safely, but pgvector is a server extension and
    no project dependency should register a global adapter just to serialize a
    list. Decimal strings preserve the provider's floats; rejecting NaN and
    infinity makes a provider defect a clear indexing failure rather than a
    malformed SQL value.
    """
    if not vector or not all(math.isfinite(value) for value in vector):
        raise ValueError("embedding must contain at least one finite number")
    return "[" + ",".join(format(value, ".17g") for value in vector) + "]"


class PgVectorBackend:
    """Pgvector implementation of VectorBackend.

    Every row carries the same three scope fields Qdrant filters on. The SQL
    clause is produced in one place and shared by index replacement, retrieval,
    and project reclamation, so a new call site cannot accidentally rank across
    tenants. `user_key` always resolves to ``default`` when omitted, matching
    Qdrant's legacy single-user behavior.

    A bare ``vector`` column deliberately permits multiple dimensions. Pgvector
    documents expression/partial HNSW indexes for that shape; choosing one needs
    production traffic by model and dimension, so this first implementation
    keeps the universally-valid scope btree and avoids prematurely optimizing a
    workload it has not measured.
    """

    def __init__(
        self,
        settings: RAGSettings,
        embeddings: Embeddings,
        *,
        connection_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.settings = settings
        self.embeddings = embeddings
        dsn = settings.database_url or settings.supabase_db_url
        if not dsn:
            raise ValueError("VECTOR_BACKEND=pgvector requires DATABASE_URL or SUPABASE_DB_URL")
        self.dsn: str = dsn
        self._connection_factory = connection_factory or self._default_connection
        self._schema_ready = False

    def _default_connection(self) -> Any:
        try:
            from psycopg import connect
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError(
                "pgvector support is optional; install it with `uv sync --group pgvector`"
            ) from exc
        return connect(self.dsn, row_factory=dict_row)

    def _connection(self) -> Any:
        return self._connection_factory()

    @staticmethod
    def _scope(
        user_key: str | None,
        project_id: str | None = None,
        embedding_signature: str | None = None,
    ) -> tuple[str, tuple[str, ...]]:
        clauses = ["user_key = %s"]
        values: list[str] = [user_key or "default"]
        if project_id is not None:
            clauses.append("project_id = %s")
            values.append(project_id)
        if embedding_signature is not None:
            clauses.append("embedding_signature = %s")
            values.append(embedding_signature)
        return " AND ".join(clauses), tuple(values)

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        with self._connection() as connection, connection.cursor() as cursor:
            for statement in _SCHEMA:
                cursor.execute(statement)
        self._schema_ready = True

    @staticmethod
    def _tag(
        chunk: Document,
        user_key: str | None,
        project_id: str | None,
        embedding_signature: str | None,
    ) -> dict[str, Any]:
        metadata = dict(chunk.metadata)
        metadata["user_key"] = user_key or metadata.get("user_key") or "default"
        if project_id is not None:
            metadata["project_id"] = project_id
        if embedding_signature is not None:
            metadata["embedding_signature"] = embedding_signature
        return metadata

    def _replace_sync(
        self,
        chunks: list[Document],
        vectors: list[list[float]],
        user_key: str | None,
        project_id: str | None,
        embedding_signature: str | None,
    ) -> None:
        self._ensure_schema()
        scope, scope_values = self._scope(user_key, project_id)
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {_TABLE} WHERE {scope}", scope_values)
            self._insert(cursor, chunks, vectors, user_key, project_id, embedding_signature)

    def _add_sync(
        self,
        chunks: list[Document],
        vectors: list[list[float]],
        user_key: str | None,
        project_id: str | None,
        embedding_signature: str | None,
    ) -> None:
        self._ensure_schema()
        with self._connection() as connection, connection.cursor() as cursor:
            self._insert(cursor, chunks, vectors, user_key, project_id, embedding_signature)

    def _insert(
        self,
        cursor: Any,
        chunks: list[Document],
        vectors: list[list[float]],
        user_key: str | None,
        project_id: str | None,
        embedding_signature: str | None,
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(
                "embedding provider returned a vector count that does not match chunks"
            )
        statement = f"""
            INSERT INTO {_TABLE}
              (user_key, project_id, embedding_signature, source, content, metadata, embedding, dimensions)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::vector, %s)
        """
        for chunk, vector in zip(chunks, vectors, strict=True):
            metadata = self._tag(chunk, user_key, project_id, embedding_signature)
            resolved_user = str(metadata["user_key"])
            cursor.execute(
                statement,
                (
                    resolved_user,
                    project_id,
                    embedding_signature,
                    str(metadata.get("source", "unknown")),
                    chunk.page_content,
                    json.dumps(metadata, default=str),
                    _vector_literal(vector),
                    len(vector),
                ),
            )

    def _embed_documents(self, chunks: list[Document]) -> list[list[float]]:
        return self.embeddings.embed_documents([chunk.page_content for chunk in chunks])

    async def index(
        self,
        chunks: list[Document],
        *,
        source_names: list[str] | None = None,
        persona: str = "",
        user_key: str | None = None,
        project_id: str | None = None,
        embedding_signature: str | None = None,
    ) -> dict[str, Any] | None:
        vectors = await asyncio.to_thread(self._embed_documents, chunks) if chunks else []
        await asyncio.to_thread(
            self._replace_sync, chunks, vectors, user_key, project_id, embedding_signature
        )
        return await asyncio.to_thread(self.metadata)

    async def add(
        self,
        chunks: list[Document],
        *,
        source_names: list[str] | None = None,
        persona: str = "",
        user_key: str | None = None,
        project_id: str | None = None,
        embedding_signature: str | None = None,
    ) -> dict[str, Any] | None:
        if chunks:
            vectors = await asyncio.to_thread(self._embed_documents, chunks)
            await asyncio.to_thread(
                self._add_sync, chunks, vectors, user_key, project_id, embedding_signature
            )
        return await asyncio.to_thread(self.metadata)

    async def remove(self, source: str) -> dict[str, Any] | None:
        await asyncio.to_thread(self._remove_sync, source)
        return await asyncio.to_thread(self.metadata)

    def _remove_sync(self, source: str) -> None:
        self._ensure_schema()
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {_TABLE} WHERE source = %s", (source,))

    def _retrieve_sync(
        self,
        vector: list[float],
        resolved_k: int,
        scope: str,
        scope_values: tuple[str, ...],
        threshold: float | None,
    ) -> list[tuple[Document, float | None]]:
        self._ensure_schema()
        vector_literal = _vector_literal(vector)
        threshold_clause = ""
        parameters: tuple[object, ...] = (vector_literal, *scope_values)
        if threshold is not None and threshold > 0:
            threshold_clause = " AND 1 - (embedding <=> %s::vector) >= %s"
            parameters = (*parameters, vector_literal, threshold)
        parameters = (*parameters, vector_literal, resolved_k)
        statement = f"""
            SELECT content, metadata, 1 - (embedding <=> %s::vector) AS score
            FROM {_TABLE}
            WHERE {scope}{threshold_clause}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            rows = cursor.fetchall()
        return [
            (
                Document(page_content=str(row["content"]), metadata=dict(row["metadata"])),
                float(row["score"]),
            )
            for row in rows
        ]

    async def retrieve(
        self,
        query: str,
        *,
        k: int | None = None,
        search_type: str | None = None,
        min_score: float | None = None,
        user_key: str | None = None,
        project_id: str | None = None,
        embedding_signature: str | None = None,
    ) -> list[tuple[Document, float | None]]:
        vector = await asyncio.to_thread(self.embeddings.embed_query, query)
        scope, scope_values = self._scope(user_key, project_id, embedding_signature)
        threshold = self.settings.score_threshold if min_score is None else min_score
        return await asyncio.to_thread(
            self._retrieve_sync,
            vector,
            max(k or self.settings.top_k, 1),
            scope,
            scope_values,
            threshold,
        )

    def clear_project(self, user_key: str | None, project_id: str) -> None:
        self._ensure_schema()
        scope, scope_values = self._scope(user_key, project_id)
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {_TABLE} WHERE {scope}", scope_values)

    def metadata(self) -> dict[str, Any] | None:
        try:
            with self._connection() as connection, connection.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) AS chunk_count FROM {_TABLE}")
                row = cursor.fetchone()
        except Exception:
            return None
        if row is None:
            return None
        return {
            "embedding_provider": self.settings.embedding_provider,
            "embedding_model": self.settings.embedding_model,
            "chunk_size": self.settings.chunk_size,
            "chunk_overlap": self.settings.chunk_overlap,
            "chunk_count": int(row["chunk_count"]),
            "backend": "pgvector",
            "table": _TABLE,
        }

    def exists(self) -> bool:
        return self.metadata() is not None

    def invalidate_cache(self) -> None:
        # Connections are short-lived. There is no in-memory index to invalidate.
        return None

    def reset(self) -> None:
        self._ensure_schema()
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {_TABLE}")
