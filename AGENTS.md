# AGENTS.md

Guidance for Codex when working in this repository.

## What Sentient is

A RAG backend for AI-driven NPC dialogue in games. Today it serves the Mantella Skyrim mod through
an OpenAI-compatible `/v1/chat/completions` adapter (FastAPI + LangChain, FAISS local index,
multi-provider LLMs). It is mid-refactor into a **multi-project AI runtime**: one deployment, many
users, many game "projects" — each project a database row owning its config, **one editable
persona** (per game, never per NPC), documents, and chat threads. Direction and contracts live in
`docs/superpowers/plans/2026-07-07-sentient-world-runtime-overview.md`; the remaining backlog in
`docs/superpowers/plans/2026-08-11-post-R8-launch-todo.md`. (There is no `order.md`; R9 writes
one.) Plans 01 (async VectorBackend seam) and 02 (Qdrant hybrid backend), R1–R7 (Neon Postgres
state, Neon Auth, RuntimeContext, routing, concurrency, reindex guard, encrypted user credentials
+ per-thread memory) and R8 (mainline port: startup warmup, STT proxy + mic diagnostics, resource
lifecycle, deployable container) are **all implemented on `dev`**.

Three gaps remain. **Verification:** V1 has been run and **passes** (2026-08-15) after fixing the
two blockers it found — `docs/superpowers/verification/2026-08-13-V1-results.md`. V2 and V3 are
still unrun, so `logic/state/postgres_store.py` and the Qdrant payload filters are fake-only today.
**Structure:** `api.py` is 1720 lines — 32% of the backend — mixing routing, schemas, DI, domain
logic and a Supabase CRUD adapter; there is no lint, type-check or CI. **Frontend:** `frontend/`
has no UI for the credential vault, thread sidebar, or R8 lifecycle/document endpoints.

**Next up is R9**, the modular-monolith refactor:
`docs/superpowers/specs/2026-08-13-r9-modular-monolith-design.md` (design approved, implementation
plan deliberately unwritten). **V1 is done; do not start R9 until V2 and V3 have actually been
run.** When running a gate, print the config the harness resolved (provider, model, threshold)
before reporting any number — V1 produced one false positive from a harness that silently
resolved a different embedding provider than the server.

**Plan documents have drifted from the code.** Several quote 125 tests; the suite collects 200 as
of 2026-08-15. Never copy a test count or file list out of an older plan — regenerate it.

## Commands

```bash
uv run python -m pytest tests/ -v          # full test suite (the DoD gate for every plan task)
uv run python -m pytest tests/test_qdrant_backend.py -v   # one file
uv run uvicorn api:app --port 8000         # run the API
uv add <package>                           # deps via uv only; never hand-edit uv.lock
```

## Architecture

- `api.py` — all 40 FastAPI routes plus 15 Pydantic models, DI builders, the ingest/reindex
  handlers, and a Supabase CRUD adapter. R4 removed the global `brain`; clients now resolve per
  turn from `RuntimeContext`. **Two chat-history systems coexist here:** legacy `chat_sessions`
  (`/v1/chats`, `client_id`-keyed, what `frontend/` uses) and R7's `chat_threads`/`chat_messages`
  (project-scoped, in the state store). R9/F0 deletes the legacy one — do not build on it.
- `logic/config.py` — the ONLY place env vars are read; exposes frozen `RAGSettings` via
  `load_rag_settings()`. Every new knob goes here (`_env_int`/`_env_float`/`_env_bool` helpers).
- `logic/retrieval/` — the async `VectorBackend` Protocol (`base.py`), `FaissBackend`
  (`faiss_store.py`, default), `QdrantBackend` (`qdrant_store.py`, hybrid dense+sparse BM25/RRF,
  SQ8, tenant/project payload filters), selected by `get_vector_backend` (`factory.py`) on
  `VECTOR_BACKEND`.
- `logic/ingestion.py` — `ArchivesIngestion`: PDF/TXT load, split, OCR, delegates storage to the
  backend. `logic/rag_engine.py` — `NPCBrain` (prompt + retrieval + answer).
- `logic/openai_adapter.py` — OpenAI wire-format translation + SSE streaming.
  `logic/sqlite_chat_store.py` / Supabase — legacy chat history (deleted by R9/F0).
  `frontend/` — static test UI, pre-refactor; base URL and `/v1/chats` calls are both wrong.
- `logic/state/` — the async `StateStore` Protocol (`base.py`), `SQLiteStateStore` (default,
  `data/state.db`) and `PostgresStateStore` (asyncpg; Neon *and* Supabase — only the DSN differs),
  selected by `get_state_store` on `DATABASE_URL`. Owns users, api_keys, projects, project_configs,
  documents, provider_credentials, chat_threads, chat_messages.
- `logic/runtime.py` — `RuntimeContext` (per-request tenant resolution), `embedding_signature`,
  `RuntimeCache`. `logic/auth.py` — API-key hashing + JWT/JWKS identity, `IdentityCache`.
- `logic/workers.py` — `IngestQueue`, `SessionLocks`, `defer` (in-process, not crash-durable).
  `logic/registry.py` — `ObjectRegistry`, single-flight client cache keyed by config signature.
- `logic/credentials.py` — Fernet encrypt/decrypt for the credential vault. `logic/memory.py` —
  per-session `SessionMemory` deque. `logic/condense.py` — query condensation.
- `logic/stt.py` — STT provider/credential resolution + cached upstream client for the optional
  `/v1/audio/transcriptions` proxy. `logic/audio_diagnostics.py` — pure numpy/`wave` WAV
  measurement; thresholds are fitted to real captures, do not retune without new measurements.
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
override its body text; the newest delta wins. The launch backlog carries the gates and sequencing.
Personas are per-project (`project_configs.persona_prompt`): do not reintroduce per-NPC persona
tables or `npc_name`-keyed config resolution.
