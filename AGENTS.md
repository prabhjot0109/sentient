# AGENTS.md

Guidance for Codex when working in this repository.

## What Sentient is

A RAG backend for AI-driven NPC dialogue in games. Today it serves the Mantella Skyrim mod through
an OpenAI-compatible `/v1/chat/completions` adapter (FastAPI + LangChain, FAISS local index,
multi-provider LLMs). It is mid-refactor into a **multi-project AI runtime**: one deployment, many
users, many game "projects" — each project a database row owning its config, **one editable
persona** (per game, never per NPC), documents, and chat threads. Start at
`docs/superpowers/plans/order.md` — it is the single source of truth for what is done and what is
next; the architecture lives in
`docs/superpowers/specs/2026-07-07-sentient-world-runtime-overview.md` and the backlog in
`docs/superpowers/plans/2026-08-11-post-R8-launch-todo.md`.

Plans 01–03, R1–R7, R8, V1 and **R9 (the modular-monolith refactor) are all done on `dev`**. R9
replaced the 1,727-line `api.py` with a four-layer package under `src/sentient/`, deleted the
legacy chat-session system, and added ruff, mypy, import-linter and CI.

**DEV-2: R9 ran after V1 only. V2 and V3 are still unrun** — `adapters/state/postgres_store.py`
and the Qdrant payload filters remain fake-only today, and both gates stay BLOCKER-grade before
any Phase F task starts. When running a gate, print the config the harness resolved (provider,
model, threshold, paths) before reporting any number — V1 produced one false positive from a
harness that silently resolved a different embedding provider than the server.

**Plan documents have drifted from the code.** Several quote 125 or 200 tests; the suite collects
**209** as of 2026-08-15. Each plan file also carries 🔶 DELTA banners that override its body text,
newest delta wins. Never copy a test count, file list, or "state at time of writing" line out of a
plan — regenerate it, and confirm a referenced file exists before relying on it.

## Commands

```bash
uv run python -m pytest tests/ -v          # full test suite (the DoD gate for every plan task)
uv run python -m pytest tests/test_qdrant_backend.py -v   # one file
uv run uvicorn sentient.api.app:app --port 8000           # run the API
uv run ruff check src tests                # lint
uv run ruff format --check src tests       # format gate
uv run mypy src/sentient/core src/sentient/adapters       # strict typing on the Protocol seams
uv run lint-imports                        # the layer contract
uv add <package>                           # deps via uv only; never hand-edit uv.lock
```

CI (`.github/workflows/ci.yml`) runs all five on every push and pull request.

## Architecture — four layers, one direction

Dependencies point one way only: **`api → services → adapters → core`**. `import-linter` enforces
it; a violation is an architectural regression, so move the code rather than weaken the contract.

- **`core/`** — no I/O, no framework. `config.py` is the ONLY place env vars are read (frozen
  `RAGSettings` via `load_rag_settings()`; every new knob goes here with the
  `_env_int`/`_env_float`/`_env_bool` helpers). `errors.py` holds the HTTP-free domain exception
  hierarchy routers translate to status codes. Also `cache.py` (`ObjectRegistry` single-flight
  client cache), `concurrency.py` (`IngestJob`, `IngestQueue`, `SessionLocks`, `defer` — in-process,
  not crash-durable), `crypto.py` (Fernet vault primitives), `presets.py`.
- **`adapters/`** — everything that talks to the outside world. `state/` is the async `StateStore`
  Protocol (`base.py`) with `SQLiteStateStore` (default, `data/state.db`) and `PostgresStateStore`
  (asyncpg; Neon *and* Supabase — only the DSN differs); it owns users, api_keys, projects,
  project_configs, documents, provider_credentials, chat_threads, chat_messages. `retrieval/` is the
  async `VectorBackend` Protocol with `FaissBackend` (default) and `QdrantBackend` (hybrid
  dense+sparse BM25/RRF, SQ8, tenant/project payload filters), selected by `factory.py` on
  `VECTOR_BACKEND`. `llm/` holds `models.py` (provider client construction), `openai_wire.py` (wire
  translation + SSE) and `persona.py`. `documents.py` is `ArchivesIngestion` (PDF/TXT load, split,
  OCR). `auth.py` is API-key hashing + JWT/JWKS identity + `IdentityCache`. `stt/` is provider
  resolution and the pure numpy/`wave` WAV diagnostics — its thresholds are fitted to real
  captures, so do not retune them without new measurements.
- **`services/`** — domain logic, no FastAPI. `rag.py` (`NPCBrain`), `runtime.py`
  (`RuntimeContext` per-request tenant resolution, `embedding_signature`, `RuntimeCache`),
  `chat.py`, `ingestion.py`, `projects.py`, `credentials.py`, `transcription.py`, `condense.py`,
  `memory.py`.
- **`api/`** — HTTP only. `app.py` is a 112-line app factory: lifespan, CORS, nine
  `include_router` calls, nothing else. `deps.py` is the composition root holding every
  module-level singleton. `routers/` holds the nine routers (none over 250 lines) and `schemas/`
  the Pydantic bodies.

`apps/` holds the two Node apps, both outside every backend gate (ruff/mypy/import-linter/
pytest are path-scoped to `src/` and `tests/`, so nothing there can turn CI red): `apps/web/`
is the frozen pre-refactor test UI (D4 — its chat-history sidebar is *expected* to be broken
since B0; F5 rebuilds it on threads), and `apps/landing/` is the marketing site, deliberately
unwired — its Launch CTA is a plain link and auth happens in `apps/web`, which is what lets
the two stay separate builds with no cross-origin token handoff. Each has its own
`AGENTS.md`, `package.json` and npm lockfile; there is no workspace tool (D5).

`cli.py` is the `sentient` console script. `migrations/` holds the `.sql` files
`PostgresStateStore` applies on first connect. `config/config.ini` is **Mantella's** config, checked
in as reference wiring only — Sentient never reads it; Mantella reads
`Documents/My Games/Mantella/config.ini`. `tests/` is `unittest.TestCase` /
`IsolatedAsyncioTestCase` under a pytest runner.

## Hard constraints (from the runtime overview §8 — apply to all new code)

- **Routers import the deps MODULE, never names out of it** (spec §7.1):

  ```python
  from sentient.api import deps      # correct
  deps.state_store                   # resolved at call time, so patching works

  from sentient.api.deps import state_store   # WRONG
  ```

  The name form binds the value at import time, so a test patching `deps.state_store` would have
  no effect and the router would keep using the real store — a test passing for the wrong reason.
  No type checker or linter catches this; `tests/test_layer_rule.py` pins it instead.
- **Singletons stay module-level in `deps.py`** (spec §7.2). Do not convert them to FastAPI
  `dependency_overrides`.
- **Async-native:** no blocking I/O on the event loop. Sync CPU work goes through
  `asyncio.to_thread`; `asyncio.Lock` is acquired at coroutine level, never held across a
  `to_thread`, and cached per event loop (see `_get_index_lock` in `faiss_store.py`).
- **Defaults preserve behavior:** `VECTOR_BACKEND=faiss`, no `DATABASE_URL` ⇒ SQLite, flags off.
  A fresh clone must behave like `main`. Back-compat on existing endpoints is a hard constraint.
- **No network in tests:** Qdrant uses `location=":memory:"`, fake embeddings, patched clients.
- **Clients connect over `127.0.0.1`, never `localhost`.** Uvicorn binds IPv4 only and Windows
  resolves `localhost` to `::1` first: measured 208 ms of wasted connect time per request,
  invisible in server-side logs. See README "Latency: what actually matters".
- Python ≥3.12, LangChain <1.0.0. TDD per task: failing test → green → commit
  (`feat:`/`refactor:`/`test:`/`docs:`/`chore:` prefixes, one commit per task).
- `.env.example` + `README.md` updated in the same change that adds a flag.

## Working on the refactor

Read `plans/order.md` first, then the specific plan file — each carries 🔶 DELTA banners that
override its body text; the newest delta wins. Personas are per-project
(`project_configs.persona_prompt`): do not reintroduce per-NPC persona tables or `npc_name`-keyed
config resolution. `docs/` is deliberately local-only and **is** ignored by git (`.gitignore` has
`/docs`), so `git add -A` is safe and plan files never enter a commit.
