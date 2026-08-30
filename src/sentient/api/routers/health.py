"""Liveness and readiness, kept as two routes because they answer two questions.

Per spec D6 no service is created for a passthrough: this reads the default
archive and the resolved settings directly.

`/health` is liveness. "This process is running." It is cheap, already consumed,
and correct for what it does.

`/health/ready` is readiness. "This instance can serve a request." The distinction
is not pedantry: the two have different consumers and opposite remedies. A failed
liveness check means restart the process; a failed readiness check means take the
instance out of rotation and leave it alone. Conflating them turns a slow database
into a restart loop.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from sentient.api import deps
from sentient.core.config import load_rag_settings

router = APIRouter()

# A user id no `ensure_user` call can mint: real ones are Neon Auth subs or UUIDs.
# `list_projects` against it runs a real query over a real connection and comes
# back empty, which is the cheapest way to ask the database whether it is there
# without writing anything or depending on a row existing.
_PROBE_USER_ID = "__readiness_probe__"


@router.get("/health")
def health_check():
    archives = deps.get_default_archives()
    settings = load_rag_settings()
    index_metadata = archives.get_index_metadata()

    return {
        "status": "online",
        "brain_loaded": deps.object_registry.size() > 0,
        "index_loaded": archives.index_exists(),
        "source_count": len(archives.list_sources()),
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "search_type": settings.search_type,
        "top_k": settings.top_k,
        "persona": index_metadata.get("persona") if index_metadata else None,
        "index_metadata": index_metadata,
    }


@router.get("/health/ready")
async def readiness():
    """Readiness, as distinct from `/health`'s liveness.

    `/health` answers 200 while the database is unreachable. It reads the default
    archive, the object registry and the settings, and never touches the store, so
    a platform health check wired to it keeps a broken instance in the load
    balancer serving 500s to everyone routed there. That is the defect this route
    exists to fix, and it is why the platform must point here instead.

    Deliberately does NOT call a provider. A readiness probe that costs an LLM call
    bills on a 30-second timer forever and pulls the service out of rotation
    whenever the provider has a bad minute -- an outage manufactured by the thing
    watching for outages.

    Queue depths ride along because nothing else exposes them and they are the one
    number that predicts the stuck-ingest failure mode. They are reported, never
    asserted on: a deep queue is busy, not unhealthy, and failing readiness on it
    would remove the instance exactly when it has the most work in flight.
    """
    checks: dict[str, object] = {}
    ready = True

    try:
        await deps.state_store.list_projects(_PROBE_USER_ID)
        checks["state_store"] = "ok"
    except Exception as exc:  # noqa: BLE001 - a probe reports failures, it does not raise
        checks["state_store"] = f"failed: {type(exc).__name__}"
        ready = False

    checks["ingest_queue_depth"] = deps.ingest_queue.depth()
    checks["reindex_queue_depth"] = deps.reindex_queue.depth()

    return JSONResponse(
        {"ready": ready, "checks": checks},
        status_code=200 if ready else 503,
    )
