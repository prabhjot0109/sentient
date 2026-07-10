from __future__ import annotations

import os

from logic.config import RAGSettings
from logic.state.base import StateStore
from logic.state.sqlite_store import SQLiteStateStore


def get_state_store(settings: RAGSettings) -> StateStore:
    if settings.db_backend in {"neon", "supabase"}:
        dsn = settings.supabase_db_url if settings.db_backend == "supabase" else settings.database_url
        dsn = dsn or settings.database_url
        if dsn:
            from logic.state.postgres_store import PostgresStateStore
            return PostgresStateStore(dsn)
    return SQLiteStateStore(os.path.join(settings.data_dir, "state.db"))
