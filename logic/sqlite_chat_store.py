from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteChatStore:
    """Chat history persisted in a local SQLite database.

    Mirrors the method surface of the previous JSON store (list/get/create/
    update/delete) so the API layer is agnostic to the backing storage. Each
    record's messages are stored as a JSON text column, so the dicts returned
    here match the shape the API's serializers already expect.
    """

    def __init__(self, storage_path: str = "data/chat_sessions.db"):
        self.storage_path = Path(storage_path)
        self._lock = threading.Lock()
        self._ensure_storage()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.storage_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_storage(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    preview TEXT NOT NULL DEFAULT '',
                    messages TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_sessions_client_id "
                "ON chat_sessions (client_id)"
            )

    def _row_to_record(self, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "client_id": row["client_id"],
            "title": row["title"],
            "preview": row["preview"],
            "messages": json.loads(row["messages"] or "[]"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list(self, client_id: str) -> list[dict]:
        with self._lock, closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM chat_sessions WHERE client_id = ? "
                "ORDER BY updated_at DESC",
                (client_id,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get(self, chat_id: str, client_id: str) -> dict | None:
        with self._lock, closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM chat_sessions WHERE id = ? AND client_id = ?",
                (chat_id, client_id),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def create(
        self,
        *,
        client_id: str,
        title: str,
        preview: str,
        messages: list[dict],
    ) -> dict:
        timestamp = _now()
        record = {
            "id": str(uuid4()),
            "client_id": client_id,
            "title": title or "New chat",
            "preview": preview,
            "messages": messages,
            "created_at": timestamp,
            "updated_at": timestamp,
        }

        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO chat_sessions "
                "(id, client_id, title, preview, messages, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    record["id"],
                    record["client_id"],
                    record["title"],
                    record["preview"],
                    json.dumps(record["messages"], ensure_ascii=True),
                    record["created_at"],
                    record["updated_at"],
                ),
            )

        return record

    def update(
        self,
        chat_id: str,
        *,
        client_id: str,
        title: str,
        preview: str,
        messages: list[dict],
    ) -> dict | None:
        timestamp = _now()
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "UPDATE chat_sessions "
                "SET title = ?, preview = ?, messages = ?, updated_at = ? "
                "WHERE id = ? AND client_id = ?",
                (
                    title or "New chat",
                    preview,
                    json.dumps(messages, ensure_ascii=True),
                    timestamp,
                    chat_id,
                    client_id,
                ),
            )
            if cursor.rowcount == 0:
                return None

            row = connection.execute(
                "SELECT * FROM chat_sessions WHERE id = ? AND client_id = ?",
                (chat_id, client_id),
            ).fetchone()

        return self._row_to_record(row) if row else None

    def delete(self, chat_id: str, client_id: str) -> dict | None:
        with self._lock, closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT * FROM chat_sessions WHERE id = ? AND client_id = ?",
                (chat_id, client_id),
            ).fetchone()
            if row is None:
                return None

            record = self._row_to_record(row)
            connection.execute(
                "DELETE FROM chat_sessions WHERE id = ? AND client_id = ?",
                (chat_id, client_id),
            )

        return record
