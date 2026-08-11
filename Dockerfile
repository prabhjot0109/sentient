FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source code. db/migrations is required at runtime: PostgresStateStore applies
# every .sql file in it the first time it opens a pool, so a container without this
# directory dies on its first database call.
COPY npc_brain.py api.py ./
COPY logic/ logic/
COPY db/ db/

# data/ is deliberately NOT copied. It is per-tenant runtime state (uploads, FAISS
# partitions, SQLite) and belongs on a mounted volume, not baked into the image.
VOLUME ["/app/data"]

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
