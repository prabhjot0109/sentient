from __future__ import annotations

import os
import unittest
from typing import Any
from unittest.mock import patch

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from sentient.adapters.retrieval.base import VectorBackend
from sentient.adapters.retrieval.factory import get_vector_backend
from sentient.core.config import load_rag_settings


class _Embeddings(Embeddings):
    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), float(text.count("lore")), 1.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


class _Cursor:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, statement: str, parameters: tuple[object, ...] = ()) -> None:
        self.connection.commands.append((statement, parameters))

    def fetchall(self) -> list[dict[str, Any]]:
        return self.connection.rows

    def fetchone(self) -> dict[str, Any] | None:
        return self.connection.row


class _Connection:
    def __init__(self) -> None:
        self.commands: list[tuple[str, tuple[object, ...]]] = []
        self.rows: list[dict[str, Any]] = []
        self.row: dict[str, Any] | None = None

    def __enter__(self) -> _Connection:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def cursor(self) -> _Cursor:
        return _Cursor(self)


class PgVectorBackendTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.env = patch.dict(
            os.environ,
            {"VECTOR_BACKEND": "pgvector", "DATABASE_URL": "postgresql://example.test/sentient"},
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)

        from sentient.adapters.retrieval.pgvector_store import PgVectorBackend

        self.connection = _Connection()
        self.backend = PgVectorBackend(
            load_rag_settings(), _Embeddings(), connection_factory=lambda: self.connection
        )

    def _command(self, fragment: str) -> tuple[str, tuple[object, ...]]:
        return next(command for command in self.connection.commands if fragment in command[0])

    async def test_index_stamps_every_tenant_scope_on_the_row(self) -> None:
        await self.backend.index(
            [Document(page_content="A's secret lore", metadata={"source": "a.txt"})],
            user_key="tenant-a",
            project_id="a-project",
            embedding_signature="model-a",
        )

        delete, delete_parameters = self._command("DELETE FROM sentient_vectors")
        self.assertIn("user_key = %s", delete)
        self.assertIn("project_id = %s", delete)
        self.assertEqual(delete_parameters, ("tenant-a", "a-project"))

        insert, parameters = self._command("INSERT INTO sentient_vectors")
        self.assertIn("%s::vector", insert)
        self.assertEqual(parameters[0:4], ("tenant-a", "a-project", "model-a", "a.txt"))
        self.assertEqual(parameters[4], "A's secret lore")
        self.assertEqual(parameters[-2], "[15,1,1]")
        self.assertEqual(parameters[-1], 3)

    async def test_retrieve_filters_before_ranking_and_returns_the_owners_chunk(self) -> None:
        """The strong isolation assertion: B gets B's own lore, never A's.

        An empty result would prove nothing -- a missing filter and an empty table
        are indistinguishable. The fake DB therefore returns B's positive control,
        while the statement inspection proves the database was told to apply all
        three scope fields before its cosine-distance ordering.
        """
        self.connection.rows = [
            {
                "content": "B's own archive says the blue moon is safe.",
                "metadata": {"source": "b.txt", "user_key": "tenant-b"},
                "score": 0.93,
            }
        ]

        got = await self.backend.retrieve(
            "blue moon", user_key="tenant-b", project_id="b-project", embedding_signature="model-b"
        )

        self.assertEqual(got[0][0].page_content, "B's own archive says the blue moon is safe.")
        self.assertIs(type(got[0][1]), float)
        query, parameters = self._command("ORDER BY embedding <=>")
        self.assertIn("user_key = %s", query)
        self.assertIn("project_id = %s", query)
        self.assertIn("embedding_signature = %s", query)
        self.assertEqual(parameters[1:4], ("tenant-b", "b-project", "model-b"))

    def test_clear_project_is_scoped_to_the_deleted_projects_partition(self) -> None:
        self.backend.clear_project("tenant-a", "a-project")

        statement, parameters = self._command("DELETE FROM sentient_vectors")
        self.assertIn("user_key = %s", statement)
        self.assertIn("project_id = %s", statement)
        self.assertEqual(parameters, ("tenant-a", "a-project"))

    def test_factory_selects_pgvector_and_the_backend_matches_the_protocol(self) -> None:
        from sentient.adapters.retrieval.pgvector_store import PgVectorBackend

        backend = get_vector_backend(load_rag_settings(), "unused", _Embeddings())
        self.assertIsInstance(backend, PgVectorBackend)
        self.assertIsInstance(self.backend, VectorBackend)

    def test_pgvector_requires_the_same_postgres_dsn_as_state(self) -> None:
        from sentient.adapters.retrieval.pgvector_store import PgVectorBackend

        with (
            patch.dict(os.environ, {"DATABASE_URL": "", "SUPABASE_DB_URL": ""}, clear=False),
            self.assertRaisesRegex(ValueError, "DATABASE_URL"),
        ):
            PgVectorBackend(load_rag_settings(), _Embeddings())

    async def test_empty_project_rebuild_clears_only_the_project_partition(self) -> None:
        import tempfile

        from sentient.adapters.documents import ArchivesIngestion

        with tempfile.TemporaryDirectory() as empty_dir:
            archives = ArchivesIngestion(
                data_dir=empty_dir,
                index_path=empty_dir,
                settings=load_rag_settings(),
            )
            archives.backend = self.backend
            await archives.rebuild_index(
                empty_dir,
                user_key="tenant-a",
                project_id="a-project",
            )

        statement, parameters = self._command("DELETE FROM sentient_vectors")
        self.assertIn("user_key = %s", statement)
        self.assertIn("project_id = %s", statement)
        self.assertEqual(parameters, ("tenant-a", "a-project"))


if __name__ == "__main__":
    unittest.main()
