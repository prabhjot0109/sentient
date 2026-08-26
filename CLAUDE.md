# CLAUDE.md

Guidance for Claude Code when working in this repository.

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

**Since then, also done (2026-08-22/24):** phase **G** (identity, access, game-turn
persistence), **H1–H7** (the live gates and backend hardening), **B1–B3** (the console's
backend surface), **B4–B5** (error surfacing), and the console screens — **F1** (auth
shell), **F2** (projects), **F7** (API keys and the Mantella card), **F6** (the document
manager), **F5+F8** (the thread sidebar, the transcript and streamed chat) and **F3+F4**
(project settings, the persona editor and the credential vault). **V2 and V4 PASSED, and
V3 is down to Qdrant alone** — F5 closed its thread family and F3+F4 its credential family.
The frontend lives in `apps/console`; **every planned F item is built**, so a stranger can
sign in, create a project, point Mantella at it, upload lore, read or hold the conversation,
change the model, edit the persona and supply their own provider keys.

**F6 carries the async state-machine shape F5 and F3 copy** — a 202 with no document id, a
status reached only by polling `GET /v1/projects/{id}/documents`, and a project-wide reindex
layered on top. Two things it settled that both of those inherit: the poll **backs off
rather than stopping** (1.5 s / 5 s / 15 s off TanStack's own `dataUpdateCount`, never a
deadline computed from `updated_at`, which would compare the server's clock to the
browser's), and **nothing refetches `projectKeys.detail(id)` on a timer** — `useProjectQuery`
sets no `refetchInterval` and `main.tsx` builds a bare `new QueryClient()`, so any UI keyed
on `projects.status` alone updates only on a window refocus. F6 reads the reindex window off
the polled document rows instead.

**F5 found the same lesson on a shorter timescale, and F3 inherits it too: post-turn work
in `defer()` is not there when the response ends.** `POST /v1/chat` writes both messages
after the body closes — measured 2026-08-23, three trials, the transcript read **zero
messages** 406 ms after `[DONE]` and the assistant row landed 1.3–1.7 s later. A refetch
fired on `[DONE]` therefore blanks the reply the user just watched arrive.
`apps/console/src/features/threads/transcript.ts` holds the streamed draft until the
identical row appears, which is exact rather than a heuristic because `openai_wire`
persists `"".join(parts)` built from the strings it streamed — verified byte-for-byte over
the wire. Not a count (stale across turns), not a clock, and **not** "does the transcript
end with an assistant message?" (wrong on turn 2).

**F3+F4 found the same class of thing a third time, and one defect older than all of
them.** The reindex window on a one-document project is **under two seconds** — status
`reindexing_required` at t+1s, `active` at t+2s — and on an empty project it is never
observable at all, so `willReindex` predicts from the config patch and never reads
`projects.status`. Separately, **every 422 in the console rendered as "Unprocessable
Content"** until 2026-08-24: `lib/api/client.ts` treated a non-string `detail` as absent,
and FastAPI answers a validation failure with an **array**. It survived four F items because
earlier screens produced string details almost exclusively. Two more measured traps worth
carrying: `PUT /v1/projects/{id}/persona` returns the **stored config row**, not the project
detail, and `core/crypto.key_hint` **already includes its leading ellipsis**, so rendering
`…{key_hint}` doubles it.

**DEV-2: Phase V is closed. V2 PASSED 2026-08-22; V3, V5 and V6 all ran 2026-08-25 and no
BLOCKER-grade verification gap remains.** Every `PostgresStateStore` family has been driven
against real Neon, and **the Qdrant payload filters now have too** — all four isolation probes
pass against a real Qdrant 1.19.0, with the tenant filter proven at the backend seam with the
router's ownership 404 bypassed. Evidence: `docs/superpowers/verification/2026-08-24-V3-qdrant.md`
and its two siblings. The one thing still unexecuted is TLS and authenticated gRPC, because
that run used a local Docker server with no API key; it rides along with D1. When running a
gate, print the config the harness resolved (provider, model, threshold, paths) before
reporting any number — V1 produced one false positive from a harness that silently resolved a
different embedding provider than the server.

**Three Qdrant facts the V3 run measured that the FAISS default hides.** The shared collection
is created once at whatever dense dimension writes first and never revisits it, so **every
tenant on a `VECTOR_BACKEND=qdrant` deployment shares one embedding dimension** — a project
cannot move to a model of a different size, and FAISS has no such limit. `RAG_SCORE_THRESHOLD`
is a cosine floor on FAISS but a **rank-fusion artefact on Qdrant**, where pure gibberish scores
0.5 and clears the configured 0.2, so the knob is inert below 0.5; never tune it against one
backend and deploy the other. And `/health`'s `index_metadata` has a **different shape per
backend** — FAISS returns `sources` / `source_count` / `persona` / `updated_at` and no
`backend` key, Qdrant returns `backend` and `collection` and no `sources`.

**A failed reindex used to wedge a project forever, and the shape of that bug is worth
remembering.** `reindexing_required` is written both by `update_config` (meaning "a rebuild is
queued") and by `run_reindex_job`'s `except` (meaning "a rebuild failed"), and a guard that
branched on that one value could not tell them apart — so a project whose rebuild failed could
never be rebuilt, 409'ing for good while its document rows still read `ready` with
`error: null`. Fixed in `478e591` by removing the guard, since `IngestQueue` is a single FIFO
worker and `index()` clears the scope before writing, so re-enqueueing converges. **The status
column still carries both meanings**; surfacing a reindex failure to the user is open work.

**F9 adds the fourth instance of that same lesson, and one rule that outranks it: never
render `ApiError.message`.** Its constructor is `super(`${status}: ${detail}`)`, so
`.message` reads "404: project not found" — eight call sites showed users an HTTP status
they cannot act on, and three features had each hand-rolled the same four-line `message()`
helper (a fourth lived in `ChatScreen` as an inline ternary, which is why a grep for the
helper found only three). **`describe()` in `apps/console/src/lib/api/messages.ts` is now the
only place an error becomes words**; components render its `ErrorCopy` and never branch on an
error class. Where the backend wrote a sentence for a human — B4's provider text, F3+F4's
flattened 422 — pass it through rather than covering it with generic copy. Two seam facts
that go with it: a dead backend is now a typed `NetworkError` with `status: 0` (a `fetch`
rejection is a `TypeError` and never reached `toApiError`, so the one state F9 is named after
was the one the seam could not type), and a TanStack Query error is **returned, not thrown**,
so it reaches no router boundary unless a `throwOnError` predicate opts it in.

**Phase S, D6 and D8 are done (2026-08-26) and left five things worth carrying.** (1) **S1
passed live from two identities against Neon + FAISS**, and the vector probe passed in the strong
form — A's invented fact queried through B's project returned *B's own chunk*, not an empty list,
which is what distinguishes a working filter from a broken index. Frozen as 20 cases in
`tests/test_tenant_isolation.py`. (2) **`/v1/upload`, `DELETE /v1/sources/{filename}` and both
game-path routes answer 403, not 404** — they resolve through `deps.completions_ctx`, which
confirms existence where the management routes mask it, and `core/errors.py` calls that divergence
deliberate. A test written against the plan's 404 would fail against correct code. (3) **CORS must
stay the OUTERMOST middleware.** Starlette puts the last-added one in front, so the rate limiter is
added *before* it inside `api/app.py::configure_middleware()` — otherwise a 429 carries no
`Access-Control-Allow-Origin`, and a browser reports that as a network failure with no status at
all, which is the one error the console most needs to explain. (4) **Retrieved lore is appended to
the SYSTEM message**, not carried as user content (`adapters/llm/openai_wire.py:101`), so an
uploaded document speaks with the persona's own authority — there is no privilege boundary, weak or
otherwise, and the threat model is only tolerable because documents are uploaded by the project's
own owner. A shared-project feature inverts that overnight. (5) **`pymupdf` is AGPL-3.0**, a direct
dependency (`pyproject.toml:27`), imported for OCR rasterisation — it blocks a closed-source hosted
launch until it is replaced (`pypdfium2`) or licensed from Artifex. `SECURITY.md` at the repo root
states all three postures; the evidence is in `docs/superpowers/verification/2026-08-26-*`.

**The rate limiter and the token quota are both OFF by default and are not substitutes.**
`RATE_LIMIT_ENABLED` bounds *frequency* in raw-ASGI middleware (never `BaseHTTPMiddleware` — the
completions path streams SSE and defers post-response work), keyed on the api key's **hash** and
not the resolved `user_id`, because resolving that costs a database round trip on every request.
The gap is stated rather than hidden: **ten keys buy ten buckets**, and the per-user key cap that
closes it is open work. `TOKEN_QUOTA_PER_MONTH` bounds *spend*, summed from
`chat_messages.total_tokens` over a rolling 30 days, checked in the two routers before the provider
is called. `SENTIENT_SECRET_KEY_OLD` makes vault-key rotation a three-step no-downtime operation
through `MultiFernet`; **without it, changing `SENTIENT_SECRET_KEY` does not error — it silently
sends every user to the env key**, because `services/runtime.py:_stored_key` swallows the decrypt
failure by design and that fallback is correct for a single corrupt row.

**Plan documents have drifted from the code.** Several quote 125, 200, 209 or 345 tests; the
suite collects **423** as of 2026-08-26
(`uv run python -m pytest tests/ --collect-only -q | tail -1`).
Each plan file also carries 🔶 DELTA banners that override its body text, newest delta wins.
Never copy a test count, file list, or "state at time of writing" line out of a plan —
regenerate it, and confirm a referenced file exists before relying on it.

**Verify a backend shape against the running server before writing a type against it.** It
has now paid on six consecutive plans. The two state stores disagree in ways no gate
catches, and four such divergences have cost a plan revision each: `projects.created_at`
and `projects.user_id` are returned by SQLite and not by Postgres, `api_keys.revoked` is
`INTEGER` on one and `boolean` on the other, `chat_threads.prefix_hash` is returned by
SQLite only — and per METHOD on Postgres, not per store — and, found while verifying F9,
**a malformed project id crashes on Postgres and 404s on SQLite**: asyncpg refuses to *bind*
a non-UUID string to a `uuid` parameter (`DataError`, before the query is sent), so
`GET /v1/projects/does-not-exist` answers a plain-text `500` where SQLite returns `None` and
the router raises its normal 404. That one is a crash rather than a missing field, it is
**unfixed**, and it is the reason a "not found" check must use a well-formed UUID.
F3+F4 added four more that were
not divergences at all but simply wrong guesses in a plan: two response shapes, one value
that already carried its own ellipsis, and one export that already existed. Ten minutes of
`curl` against a live project turns each of those from a bug into a non-event.
`deps.current_user` accepts an `X-API-Key` as readily as a Bearer JWT, so the whole console surface can be driven from a
throwaway probe identity with no browser. `documents` and `chat_messages` were checked this
way on 2026-08-23 and **agree** on both stores — record the negatives too, or the next reader
re-measures them.

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
  `chat.py` (grounded generation, conversation-prefix thread identity, and the deferred
  transcript writer — `chat_messages` is the one durable memory for both surfaces),
  `ingestion.py`, `projects.py`, `credentials.py`, `transcription.py`, `condense.py`.
- **`api/`** — HTTP only. `app.py` is a 112-line app factory: lifespan, CORS, nine
  `include_router` calls, nothing else. `deps.py` is the composition root holding every
  module-level singleton. `routers/` holds the nine routers (none over 250 lines) and `schemas/`
  the Pydantic bodies.

`apps/` holds **three** Node apps, all outside every backend gate (ruff/mypy/import-linter/
pytest are path-scoped to `src/` and `tests/`, so nothing there can turn CI red):

- **`apps/console/`** — the real console, added 2026-08-23 (F1). Vite 8 + TanStack Router +
  Query + Tailwind 4. Layers are `routes → features → lib → types`, enforced by ESLint along
  with a ban on any `fetch` outside `lib/api/client.ts`. **Read `apps/console/AGENTS.md`
  before touching it** — it carries the measured Neon Auth SDK surface (two traps the F1 plan
  had wrong), the store divergences, and the `localhost`-vs-`127.0.0.1` rule. Its four gates
  (`npm run lint` / `test` / `build` / `npx prettier --check .`) are run by hand; wiring them
  into CI is F10.
- **`apps/web/`** — the frozen pre-refactor test UI, reference only (its chat-history sidebar
  is *expected* to be broken since B0). F12 retires it.
- **`apps/landing/`** — the marketing site. Its Launch CTA is a plain cross-origin link to the
  console's `/auth/sign-in`, which is what lets the two stay separate builds with no
  cross-origin token handoff.

Console routing has one trap worth knowing before adding a screen: flat file routes mean a
sibling file turns its neighbour into a **layout**, and a layout with no `<Outlet/>` renders
the parent and silently drops the child. The project home is `routes/app/p.$pid.index.tsx`
for that reason; `p.$pid.chat.tsx` sits beside it as a second leaf.

Each has its own `AGENTS.md`, `package.json` and npm lockfile; there is no workspace tool (D5).

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
config resolution. **The stored persona and the resolved persona are different values** — a
project whose `persona_prompt` is NULL still speaks in character from its preset, which H1's
Finding 4 measured and F7 confirmed through the game path. `GET /v1/projects/{id}` reports the
resolved one with a `persona_source` of `custom` / `preset` / `generic`; anything that reads
the stored column alone will render a blank over a live voice and overwrite it on save. `docs/` is deliberately local-only and must stay **untracked**. Do not rely on it being
gitignored: the committed `.gitignore` has a `/docs` rule, but it is routinely commented out in a
working tree, and `git check-ignore -v docs/` is the only way to know which state you are in.
**Never run `git add -A` or `git add .`** — list source and test paths explicitly in every commit,
or plan files enter the history.
