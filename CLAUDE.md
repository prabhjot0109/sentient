# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What Sentient is

A RAG backend for AI-driven NPC dialogue in games. Today it serves the Mantella Skyrim mod through
an OpenAI-compatible `/v1/chat/completions` adapter (FastAPI + LangChain, FAISS local index,
multi-provider LLMs). It is mid-refactor into a **multi-project AI runtime**: one deployment, many
users, many game "projects" — each project a database row owning its config, **one editable
persona** (per game, never per NPC), documents, and chat threads. Direction and contracts live in
`docs/superpowers/plans/2026-07-07-sentient-world-runtime-overview.md`; execution order in
`order.md`. Plans 01 (async VectorBackend seam) and 02 (Qdrant hybrid backend) and R1–R7 (Neon
Postgres state, Neon Auth, RuntimeContext, routing, concurrency, reindex guard, encrypted user
credentials + per-thread memory) are all implemented on `dev`. The remaining gap is the frontend:
`frontend/` has no UI for the credential vault or the thread sidebar, though both APIs exist.

## Commands

```bash
uv run python -m pytest tests/ -v          # full test suite (the DoD gate for every plan task)
uv run python -m pytest tests/test_qdrant_backend.py -v   # one file
uv run uvicorn api:app --port 8000         # run the API
uv add <package>                           # deps via uv only; never hand-edit uv.lock
```

## Architecture

- `api.py` — all FastAPI routes: OpenAI-compat adapter (`/v1/chat/completions`), web chat
  (`/v1/chat`), retrieval/upload/sources, chat-session persistence (Supabase or SQLite). Holds the
  global `brain` singleton that plan R4 deletes.
- `logic/config.py` — the ONLY place env vars are read; exposes frozen `RAGSettings` via
  `load_rag_settings()`. Every new knob goes here (`_env_int`/`_env_float`/`_env_bool` helpers).
- `logic/retrieval/` — the async `VectorBackend` Protocol (`base.py`), `FaissBackend`
  (`faiss_store.py`, default), `QdrantBackend` (`qdrant_store.py`, hybrid dense+sparse BM25/RRF,
  SQ8, tenant/project payload filters), selected by `get_vector_backend` (`factory.py`) on
  `VECTOR_BACKEND`.
- `logic/ingestion.py` — `ArchivesIngestion`: PDF/TXT load, split, OCR, delegates storage to the
  backend. `logic/rag_engine.py` — `NPCBrain` (prompt + retrieval + answer).
- `logic/openai_adapter.py` — OpenAI wire-format translation + SSE streaming.
  `logic/sqlite_chat_store.py` / Supabase — chat history. `frontend/` — static test UI.
- `tests/` — `unittest.TestCase` / `IsolatedAsyncioTestCase` + pytest runner.

## Hard constraints (from the runtime overview §8 — apply to all new code)

- **Async-native:** no blocking I/O on the event loop. Sync CPU work goes through
  `asyncio.to_thread`; `asyncio.Lock` is acquired at coroutine level, never held across a
  `to_thread`, and cached per event loop (see `_get_index_lock` in `faiss_store.py`).
- **Defaults preserve behavior:** `VECTOR_BACKEND=faiss`, no `DATABASE_URL` ⇒ SQLite, flags off.
  A fresh clone must behave like `main`. Back-compat on existing endpoints is a hard constraint.
- **No network in tests:** Qdrant uses `location=":memory:"`, fake embeddings, patched clients.
- Python ≥3.12, LangChain <1.0.0. TDD per task: failing test → green → commit
  (`feat:`/`refactor:`/`test:`/`docs:` prefixes, one commit per task).
- `.env.example` + `README.md` updated in the same change that adds a flag.

## Working on the refactor

Read the overview plan first, then the specific plan file — each carries 🔶 DELTA banners that
override its body text; the newest delta wins. `order.md` has the sequence and verification gates.
Personas are per-project (`project_configs.persona_prompt`): do not reintroduce per-NPC persona
tables or `npc_name`-keyed config resolution.
