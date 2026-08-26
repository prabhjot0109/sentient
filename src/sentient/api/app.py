"""The ASGI application: lifespan, CORS, and router registration.

Everything else lives one layer down. Routers are in `api/routers/`, the
singletons and DI builders in `api/deps.py`, and the domain operations in
`sentient.services`. This file exists to wire them together and to own the
process lifecycle — nothing here should grow a request handler.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sentient.api import deps
from sentient.api.middleware import RateLimitMiddleware
from sentient.api.routers import (
    audio,
    chat,
    completions,
    credentials,
    documents,
    health,
    keys,
    projects,
    threads,
)
from sentient.core.logging import configure_logging, get_logger

log = get_logger(__name__)


async def _warm_grounding_path() -> None:
    """Pay every one-off cost on the lore path before the first player line does.

    With local embeddings this is not a micro-optimisation: loading
    BAAI/bge-base-en-v1.5 takes ~9s, FAISS then has to be read off disk, and torch
    only builds its execution graph on the first real forward pass. All three would
    otherwise land on whichever utterance happens to arrive first, and that one is
    always the player's opening line of a conversation.

    It must be a real retrieval — building the client without embedding anything
    leaves the torch cost unpaid. build_embeddings is lru_cached, so warming this
    instance warms every archive that resolves to the same embedding config.
    """
    started = perf_counter()
    await deps.get_default_archives().retrieve(
        "warmup", k=1, search_type="similarity", min_score=0.0
    )
    log.info("warmup complete", extra={"seconds": round(perf_counter() - started, 1)})


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start process-local workers and drain accepted work during shutdown."""
    # First statement: everything below is entitled to log, and until this runs
    # the "sentient" logger has no handler and its records vanish.
    configure_logging(deps._settings)
    await deps.ingest_queue.start()
    await deps.reindex_queue.start()
    try:
        try:
            # The ingest queue is in-process and not crash-durable: anything left
            # in `processing` when the previous process died will never finish,
            # and F6 would show it as an in-flight ingest forever, indistinguishable
            # from a slow one. Failing them is the honest state and the user can
            # retry the upload. Wrapped deliberately -- a reconciliation failure
            # must not stop the server from starting, exactly as warmup does not.
            stuck = await deps.state_store.fail_stuck_documents()
            if stuck:
                log.warning("marked orphaned ingest rows failed", extra={"count": stuck})
        except Exception:
            log.exception("could not reconcile stuck ingest rows")

        have_provider_key = deps.any_provider_key_present()
        try:
            if have_provider_key:
                # Build the on-disk index from data/ at boot if missing, so the Mantella
                # completions path has lore to ground on. Async so startup embedding
                # never blocks the event loop. No global brain — clients resolve per turn.
                await deps.get_default_archives().ensure_index()
            else:
                log.info("no default provider key; clients initialize per request")
        except Exception:
            log.exception("startup index build failed")

        # Deliberately awaited, not deferred: uvicorn should not report the server
        # ready while a request would still race the model load. A failure here is
        # not fatal — the cost is simply paid on first use — so it must never stop
        # startup (an empty data/ directory is a normal fresh-clone state). Skipped
        # without a provider key: there is no embedding client to warm, and building
        # one would load a model no request will resolve to.
        if have_provider_key:
            try:
                await _warm_grounding_path()
            except Exception:
                log.warning("warmup skipped; the first request will be slower", exc_info=True)

        yield
    finally:
        await deps.reindex_queue.stop()
        await deps.ingest_queue.stop()
        log.info("shutdown complete")


def configure_middleware(app: FastAPI, settings) -> None:
    """Install the middleware stack. **Order is load-bearing.**

    Starlette builds the stack with the LAST-added middleware outermost, so CORS
    must be added last to end up in front of everything else. If the rate limiter
    were outermost instead, its 429 would carry no `Access-Control-Allow-Origin`
    header and a browser would report it as a network failure rather than as the
    throttle it is -- the console would lose the one error it most needs to
    explain. `tests/test_rate_limits.py` pins this rather than the comment alone.

    A function rather than module-level statements so a test can build the exact
    same stack over a fresh app with a different `settings`, instead of reloading
    this module and leaving a mutated global behind for every test after it.
    """
    if settings.rate_limit_enabled:
        app.add_middleware(RateLimitMiddleware, settings=settings)

    app.add_middleware(
        CORSMiddleware,
        # Vite picks the next free port (5174, 5175, ...) whenever 5173 is already
        # taken by another running dev server, so pin the allow-list to a regex
        # instead of a fixed port list to avoid breaking on port bumps.
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
        # Deployed frontends, from CORS_ALLOW_ORIGINS. FastAPI honours the list and the
        # regex together, so a production origin does not cost the dev-port coverage.
        allow_origins=list(settings.cors_allow_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


app = FastAPI(title="Sentient AI API", lifespan=lifespan)

configure_middleware(app, deps._settings)

app.include_router(health.router)
app.include_router(keys.router)
app.include_router(threads.router)
app.include_router(credentials.router)
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(audio.router)
app.include_router(chat.router)
app.include_router(completions.router)
