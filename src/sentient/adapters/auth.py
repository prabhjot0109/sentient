from __future__ import annotations

import asyncio
import hashlib
import secrets
from functools import lru_cache
from typing import Any, Awaitable, Callable

import jwt
from cachetools import TTLCache


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


_identity_locks: dict[tuple[int, str], asyncio.Lock] = {}


def _loop_lock(cache_key: str) -> asyncio.Lock:
    """Single-flight lock for one identity. Keyed by (event loop, identity) because
    asyncio.Lock binds to the loop it was created on — and because a lock shared
    across identities would serialize every tenant's cold auth behind one DB read."""
    lock_key = (id(asyncio.get_running_loop()), cache_key)
    lock = _identity_locks.get(lock_key)
    if lock is None:
        lock = asyncio.Lock()
        _identity_locks[lock_key] = lock
    return lock


class IdentityCache:
    """TTL cache of resolved (user_id, user_key) tuples keyed by a token/key hash.
    Keeps auth off the hot path: DB is hit at most once per identity per TTL window."""

    def __init__(self, ttl: float = 300, maxsize: int = 1024) -> None:
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)

    async def resolve(self, cache_key: str, loader: Callable[[], Awaitable[Any]]) -> Any:
        hit = self._cache.get(cache_key)
        if hit is not None:
            return hit
        lock_key = (id(asyncio.get_running_loop()), cache_key)
        try:
            async with _loop_lock(cache_key):
                hit = self._cache.get(cache_key)
                if hit is not None:
                    return hit
                value = await loader()
                self._cache[cache_key] = value
                return value
        finally:
            _identity_locks.pop(lock_key, None)

    def clear(self) -> None:
        self._cache.clear()


async def resolve_user(state, settings, *, jwt_token: str | None = None,
                       api_key: str | None = None, header_key: str | None = None,
                       cache: IdentityCache | None = None) -> tuple[str, str]:
    key = api_key or header_key

    if jwt_token and auth_enabled(settings):
        async def _load_jwt():
            claims = verify_jwt(jwt_token, settings)
            sub = claims.get("sub")
            if not sub:
                raise AuthError("token has no sub claim")
            user = await state.ensure_user(sub, claims.get("email"))
            return (user["id"], user_key_of(sub))
        ck = "jwt:" + hash_key(jwt_token)
        return await (cache.resolve(ck, _load_jwt) if cache else _load_jwt())

    if key:
        async def _load_key():
            row = await state.get_user_by_api_key_hash(hash_key(key))
            if not row or row.get("revoked"):
                raise AuthError("unknown or revoked api key")
            return (row["user_id"], user_key_of(key))
        ck = "key:" + hash_key(key)
        return await (cache.resolve(ck, _load_key) if cache else _load_key())

    default_user = await state.ensure_user(None)
    return (default_user["id"], "default")
