from __future__ import annotations

import hashlib
import secrets


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def user_key_of(identifier: str) -> str:
    """Log-safe, stable, opaque tenant id used for Qdrant payloads and cache keys."""
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:16]


def generate_api_key() -> tuple[str, str]:
    """Return (raw_key, key_hash). The raw key is shown to the user exactly once;
    only the hash is ever stored."""
    raw = "sk-sent-" + secrets.token_urlsafe(32)
    return raw, hash_key(raw)
