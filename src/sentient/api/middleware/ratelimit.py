"""D6's HTTP half: map an identity to a bucket and a refusal to a 429.

The hole this closes, stated plainly: `POST /v1/keys` is open to any
authenticated user, the vault holds other people's provider keys, and the game
route accepts a key in a URL. Without this, a public deployment is an open proxy
on someone else's provider bill.

**Raw ASGI, not `BaseHTTPMiddleware`.** The completions path streams SSE and
schedules post-response work through `core.concurrency.defer()`;
`BaseHTTPMiddleware` runs the downstream app in its own task and has a long
history of interfering with exactly those two things. This class touches the
request scope, decides, and either calls through or answers -- it never wraps
the response body.

**No locking.** `BucketRegistry.allow` does no I/O and never awaits, so it runs
to completion inside one event-loop step. Adding a lock here would serialise
every request behind the cheapest component in the system.
"""

from __future__ import annotations

import hashlib
import math
import time

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from sentient.core.config import RAGSettings
from sentient.core.limits import BucketRegistry

# The platform polls /health forever. Throttling it would pull the instance out
# of the load balancer under exactly the load this middleware exists to survive.
EXEMPT_PATHS = frozenset({"/health"})

_COMPLETIONS_SUFFIX = "/chat/completions"


def _hashed(value: bytes) -> str:
    """Bucket keys are hashes, never key material.

    Middleware sits upstream of H5's log scrubbing, so a raw key held here is one
    stray exception away from a traceback in a log file.
    """
    return hashlib.sha256(value).hexdigest()[:32]


def _key_in_path(path: str) -> str | None:
    """The Mantella shape: `/v1/<key>/chat/completions` and `/v1/<key>/<project>/…`.

    `/v1/chat/completions` has no key segment, which is why this counts segments
    rather than trusting the position.
    """
    if not path.endswith(_COMPLETIONS_SUFFIX):
        return None
    parts = [part for part in path.split("/") if part]
    return parts[1] if len(parts) >= 4 else None


class RateLimitMiddleware:
    """Per-identity token buckets, chosen by path.

    **Identity is the API key's hash, or the client host when there is none.**
    Not the resolved `user_id`, which is what tenancy is actually keyed on (G1):
    resolving it means a database round trip on every request and duplicates
    `deps.current_user`, and verifying a JWT here would add a JWKS fetch to the
    hot path. The gap that leaves is real and bounded: **a caller who mints ten
    API keys gets ten buckets.** Its complement is a per-user key cap on
    `POST /v1/keys`, raised as its own backlog item in SECURITY.md -- and the
    default bucket, which `POST /v1/keys` itself falls under, bounds how fast
    those ten can be minted in the first place.

    A console caller authenticating with a Bearer JWT therefore buckets on client
    host, which means several console users behind one NAT share a budget. That
    is the safe direction to be wrong: keying on an unverified token would let an
    attacker mint a fresh bucket per request by varying one character.
    """

    def __init__(self, app: ASGIApp, settings: RAGSettings) -> None:
        self.app = app
        self._completions = BucketRegistry(
            capacity=settings.rate_limit_completions_per_minute,
            refill_per_second=settings.rate_limit_completions_per_minute / 60.0,
        )
        self._uploads = BucketRegistry(
            capacity=settings.rate_limit_uploads_per_hour,
            refill_per_second=settings.rate_limit_uploads_per_hour / 3600.0,
        )
        self._default = BucketRegistry(
            capacity=settings.rate_limit_default_per_minute,
            refill_per_second=settings.rate_limit_default_per_minute / 60.0,
        )

    def _registry(self, path: str) -> BucketRegistry:
        if path.endswith(_COMPLETIONS_SUFFIX) or path == "/v1/chat":
            return self._completions
        if path == "/v1/upload":
            return self._uploads
        return self._default

    def _identity(self, scope: Scope) -> str:
        for name, value in scope.get("headers", ()):
            if name == b"x-api-key" and value:
                return "key:" + _hashed(value)

        path_key = _key_in_path(scope.get("path", ""))
        if path_key:
            return "key:" + _hashed(path_key.encode("utf-8"))

        client = scope.get("client")
        return "host:" + (client[0] if client else "unknown")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")
        if path in EXEMPT_PATHS:
            return await self.app(scope, receive, send)

        # monotonic, not wall time: a clock adjustment must not hand out a free
        # burst (or, going the other way, freeze a bucket for hours).
        allowed, retry_after = self._registry(path).allow(self._identity(scope), time.monotonic())
        if allowed:
            return await self.app(scope, receive, send)

        # Whole seconds and never below 1: Retry-After is an integer per RFC 9110,
        # and a rounded-down 0 would invite an immediate retry that cannot succeed.
        seconds = max(1, math.ceil(retry_after))
        response = JSONResponse(
            # `detail`, matching every other error this API produces, so the
            # console's seam types it and F9's describe() can speak for it
            # without learning a second error shape.
            {"detail": "rate limit exceeded; slow down and try again"},
            status_code=429,
            headers={"Retry-After": str(seconds)},
        )
        await response(scope, receive, send)
        return None
