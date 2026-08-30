FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

# Source is copied BEFORE `uv sync` because the project is now an installed
# package (hatchling, src/ layout): syncing builds sentient itself, so src/ and
# the README the build backend reads must already be present.
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/
# --no-default-groups, not --no-dev: it drops `local-embeddings` as well, and that
# group carries sentence-transformers, which is the only thing in this tree that
# requires torch. Measured 2026-08-31: torch costs 158 MB of resident memory and 7 s
# of cold start at import, on a host that has 512 MB total and still has to rasterise
# PDF pages during ingestion. Dropping it needs no code change because the deployment
# sets EMBEDDING_PROVIDER to a hosted provider; `build_embeddings` explains the
# missing group if anything ever selects the local one.
#
# A `uv run` in the CMD below would re-sync WITH the default groups and reinstall
# torch at boot, so the entrypoint calls the venv's uvicorn directly.
RUN uv sync --frozen --no-default-groups

# migrations/ is required at runtime: PostgresStateStore applies every .sql file
# in it the first time it opens a pool, so a container without this directory
# dies on its first database call.
COPY migrations/ migrations/

# data/ is deliberately NOT copied. It is per-tenant runtime state (uploads, FAISS
# partitions, SQLite) and belongs on a mounted volume, not baked into the image.
VOLUME ["/app/data"]

EXPOSE 8000

# The venv's uvicorn directly, NOT `uv run uvicorn`: `uv run` re-syncs the project
# environment before executing, which would honour default-groups and pull torch
# back in at container start -- undoing the --no-default-groups above, at boot, on
# every restart.
#
# ONE worker, deliberately. Every stateful component in this process is per-process:
# ObjectRegistry, IngestQueue, SessionLocks, RuntimeCache, and the rate-limit
# buckets. Two workers means two of each, so a job enqueued on worker A is invisible
# to worker B and the effective rate limit doubles. Scaling out needs a shared queue
# and a shared cache first.
CMD ["/app/.venv/bin/uvicorn", "sentient.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
