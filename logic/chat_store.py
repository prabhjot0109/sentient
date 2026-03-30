from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LocalChatStore:
    def __init__(self, storage_path: str = "data/chat_sessions.json"):
        self.storage_path = Path(storage_path)
        self._lock = threading.Lock()

    def _ensure_storage(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self.storage_path.write_text("[]", encoding="utf-8")

    def _read_all(self) -> list[dict]:
        self._ensure_storage()
        try:
            return json.loads(self.storage_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

    def _write_all(self, records: list[dict]) -> None:
        self._ensure_storage()
        self.storage_path.write_text(
            json.dumps(records, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

    def list(self, client_id: str) -> list[dict]:
        with self._lock:
            records = [
                record for record in self._read_all() if record.get("client_id") == client_id
            ]

        return sorted(
            records,
            key=lambda record: record.get("updated_at") or record.get("created_at") or "",
            reverse=True,
        )

    def get(self, chat_id: str, client_id: str) -> dict | None:
        with self._lock:
            for record in self._read_all():
                if record.get("id") == chat_id and record.get("client_id") == client_id:
                    return record
        return None

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

        with self._lock:
            records = self._read_all()
            records.append(record)
            self._write_all(records)

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
        with self._lock:
            records = self._read_all()
            for index, record in enumerate(records):
                if record.get("id") == chat_id and record.get("client_id") == client_id:
                    updated = {
                        **record,
                        "title": title or "New chat",
                        "preview": preview,
                        "messages": messages,
                        "updated_at": _now(),
                    }
                    records[index] = updated
                    self._write_all(records)
                    return updated
        return None

    def delete(self, chat_id: str, client_id: str) -> dict | None:
        with self._lock:
            records = self._read_all()
            kept_records: list[dict] = []
            removed_record: dict | None = None

            for record in records:
                if record.get("id") == chat_id and record.get("client_id") == client_id:
                    removed_record = record
                    continue
                kept_records.append(record)

            if removed_record is None:
                return None

            self._write_all(kept_records)
            return removed_record
