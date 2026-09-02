"""H8 — the Langfuse callback handler, resolved once and degrading to nothing.

Nothing in this system can currently answer *where did that turn's nine seconds
go* — retrieval, the provider, or the deferred write — and on a 0.15 CPU instance
that question has a real answer that changes what you buy. Three of Phase X's
items are explicitly gated on the measurements this produces.

Langfuse rather than raw OpenTelemetry because OTel would need every span defined
by hand for the same result, while one LangChain callback gives traces, token
usage and cost — H4 having already landed usage on the message, which is what
makes a trace show money rather than only latency. It speaks OTel underneath, so
it is not a dead end.

**Two rules, and they are the whole module.** It sits on the request path, so it
must be non-blocking, and it must degrade to a no-op when anything at all is
wrong. Every failure — the package absent, a bad key, an unreachable host, an
exception the SDK invents in a future release — resolves to `None` exactly once
and is never retried, because retrying a slow failure would add its timeout to
every NPC line.
"""

from __future__ import annotations

from typing import Any, cast

from langchain_core.callbacks.base import BaseCallbackHandler

from sentient.core.config import RAGSettings, load_rag_settings
from sentient.core.logging import get_logger

log = get_logger(__name__)

# Resolved once for the life of the process. Both the success and the failure are
# memoised: a handler is a long-lived batching client, so building one per turn is
# the opposite of what a callback handler is for, and re-attempting a failed
# construction on every request is how an observability outage becomes a latency
# regression.
#
# Not locked. Two concurrent first requests can both construct, which costs one
# redundant client and no correctness -- and a lock here would be held across a
# third-party constructor on the event loop, which is the thing this module
# exists to avoid.
_handler: BaseCallbackHandler | None = None
_resolved = False


def _construct_handler(settings: RAGSettings) -> BaseCallbackHandler:
    """Build the handler, or raise. Every caller of this treats a raise as "off".

    Split out as its own function so the failure modes above are testable without
    a Langfuse account, an unreachable host, or an uninstalled package.

    The credentials are passed to `Langfuse(...)` explicitly rather than left to
    the SDK's own `LANGFUSE_*` environment lookup. `core/config.py` is the only
    place this codebase reads configuration, and letting the SDK read its own
    would put a second, invisible source of truth beside it — one where
    `LANGFUSE_ENABLED=false` and a stray `LANGFUSE_SECRET_KEY` would still trace.
    `CallbackHandler` itself takes no secret: it resolves the client registered by
    that constructor, keyed on the public key.
    """
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

    Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
        tracing_enabled=True,
    )
    # Langfuse does not ship a usable type stub for its callback handler, so
    # mypy sees this runtime-verified BaseCallbackHandler subclass as Any.
    return cast(BaseCallbackHandler, CallbackHandler(public_key=settings.langfuse_public_key))


def get_trace_handler(settings: RAGSettings | None = None) -> BaseCallbackHandler | None:
    """The handler, or None whenever tracing is off **or** unavailable.

    `settings` is optional because Langfuse is configured per *deployment*, never
    per project: there is no tenant overlay for it, and `RuntimeContext` carries
    dicts rather than a `RAGSettings`. Callers that already hold one pass it;
    callers on the per-turn path (`openai_wire`, `services/chat`) do not, and the
    environment is read at most once for the life of the process because
    resolution is memoised either way.
    """
    global _handler, _resolved
    if _resolved:
        return _handler

    _resolved = True
    _handler = None
    settings = settings or load_rag_settings()

    if not settings.langfuse_enabled:
        return None

    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        log.warning("LANGFUSE_ENABLED is set but a key is missing; tracing is off")
        return None

    try:
        _handler = _construct_handler(settings)
    except ImportError:
        # The likeliest misconfiguration by a wide margin: the group is optional
        # and not in `default-groups`, so an operator who sets the keys without
        # rebuilding the image lands exactly here. Name the fix.
        log.warning(
            "langfuse is not installed; tracing is off "
            "(add the optional 'observability' dependency group)"
        )
    except Exception:
        # Deliberately broad. The point is that no failure of the tracer may
        # reach the caller, and an enumerated list is a promise about a
        # third-party SDK's future exception types that cannot be kept.
        log.warning("could not construct the Langfuse handler; tracing is off", exc_info=True)

    return _handler


def trace_config(settings: RAGSettings | None = None) -> dict[str, Any] | None:
    """The `config=` argument for a LangChain invoke, or None when tracing is off.

    `None` and not `{}`: it is LangChain's own default for that parameter, so the
    off path is byte-identical to the code that ran before this module existed.
    That is what makes "defaults preserve behavior" a property rather than an
    intention.
    """
    handler = get_trace_handler(settings)
    if handler is None:
        return None
    return {"callbacks": [handler]}


def reset_trace_handler() -> None:
    """Forget the memoised resolution. For tests, which would otherwise let the
    first one decide the answer for every test after it."""
    global _handler, _resolved
    _handler = None
    _resolved = False
