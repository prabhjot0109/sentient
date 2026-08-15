from __future__ import annotations

from cryptography.fernet import Fernet


def encrypt_key(raw: str, secret: str) -> str:
    return Fernet(secret.encode()).encrypt(raw.encode()).decode()


def decrypt_key(token: str, secret: str) -> str:
    return Fernet(secret.encode()).decrypt(token.encode()).decode()


def key_hint(raw: str) -> str:
    return "…" + raw[-4:]


def crypto_available(settings) -> bool:
    return bool(getattr(settings, "sentient_secret_key", None))
