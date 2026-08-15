FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

# Source is copied BEFORE `uv sync` because the project is now an installed
# package (hatchling, src/ layout): syncing builds sentient itself, so src/ and
# the README the build backend reads must already be present.
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/
RUN uv sync --frozen --no-dev

# migrations/ is required at runtime: PostgresStateStore applies every .sql file
# in it the first time it opens a pool, so a container without this directory
# dies on its first database call.
COPY migrations/ migrations/

# data/ is deliberately NOT copied. It is per-tenant runtime state (uploads, FAISS
# partitions, SQLite) and belongs on a mounted volume, not baked into the image.
VOLUME ["/app/data"]

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "sentient.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
