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


from functools import lru_cache

import jwt


class AuthError(Exception):
    """Raised when a token/key is missing, malformed, or fails verification."""


def auth_enabled(settings) -> bool:
    return bool(settings.neon_auth_jwks_url)


@lru_cache(maxsize=8)
def _jwks_client(jwks_url: str):
    # PyJWKClient fetches + caches signing keys; one instance per JWKS URL.
    return jwt.PyJWKClient(jwks_url)


def verify_jwt(token: str, settings) -> dict:
    if not auth_enabled(settings):
        raise AuthError("auth is not configured")
    try:
        signing_key = _jwks_client(settings.neon_auth_jwks_url).get_signing_key_from_jwt(token)
        options = {"verify_aud": False}  # Neon Auth tokens may omit aud; issuer is the trust anchor
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=settings.neon_auth_algorithms,
            issuer=settings.neon_auth_issuer,
            options=options,
        )
    except AuthError:
        raise
    except Exception as e:  # jwt.InvalidTokenError and friends
        raise AuthError(f"invalid token: {e}") from e
