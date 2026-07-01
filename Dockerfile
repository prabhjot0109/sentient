FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source code and data
COPY npc_brain.py api.py ./
COPY logic/ logic/
COPY data/ data/

# Expose port
EXPOSE 8000

# Run command
CMD ["uv", "run", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
