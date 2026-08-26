# Sentient

RAG backend for AI-driven NPC dialogue. Upload the documents that define a game world and Sentient
serves an OpenAI-compatible `/v1/chat/completions` endpoint that answers in character, grounded in
that lore instead of in whatever the base model happens to know.


> **Status:** local single-user deployment works today. The multi-project hosted runtime is in
> active development.

## Features

- OpenAI-compatible chat completions with SSE streaming. Existing clients need only a new base URL.
- PDF and TXT ingestion, including scanned PDFs through OCR.
- FAISS locally, or Qdrant for hybrid dense and sparse retrieval with server-side tenant filters.
- Six providers (Google, OpenAI, HuggingFace, Groq, Cerebras, OpenRouter), resolved per request.
- Project isolation: each project owns its config, persona, documents, and chat threads.
- Encrypted per-user provider credentials, API keys stored as hashes, optional JWT auth.
- Speech-to-text proxy that measures the waveform, so a failed transcription tells you whether the
  mic was dead or the model heard nothing.

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env      # add at least one provider key
uv run uvicorn sentient.api.app:app --reload
```

Interactive API docs are then at `http://127.0.0.1:8000/docs`.

Use `127.0.0.1`, never `localhost`. On Windows that one choice costs 208 ms per request; see
[performance notes](CONFIGURATION.md#performance-notes).

The console is a separate Vite app:

```bash
cd apps/console && npm install && npm run dev    # http://localhost:5175
```

**`localhost` here, `127.0.0.1` for the backend, and the two do not conflict** — they are
different hops. Neon Auth trusts the hostname `localhost` and rejects
`http://127.0.0.1:<port>` with `INVALID_ORIGIN` before it validates anything, so the console
is browsed at `localhost` while its `VITE_API_BASE_URL` stays `127.0.0.1:8000`.

From the console you can create a project per game, mint an API key and copy the Mantella
base URL, upload lore and watch it index, read and hold conversations, change the model and
retrieval settings, edit the project's persona, and store your own provider API keys.

**The provider-key vault needs `SENTIENT_SECRET_KEY`.** Without it every credential route
answers `503 credential vault is not configured` — including the listing, so the console
says the vault is unconfigured rather than that you have no keys, because the two lead to
opposite next actions. Generate one with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Rotating or removing that key leaves every stored credential undecryptable; there is no
re-encrypt path yet.

`apps/web` is the frozen pre-refactor test UI, kept for reference only; `apps/landing` is the
marketing site. Neither is the console.

## Usage

Upload lore, then point a client at the API:

```bash
curl -F "file=@lore.pdf" http://127.0.0.1:8000/v1/upload

curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"sentient","messages":[{"role":"user","content":"Who rules Skyrim?"}]}'
```

For Mantella, mint a key with `POST /v1/keys` and set `baseUrl` to
`http://127.0.0.1:8000/v1/<api_key>/<project_id>`. Mantella appends `/chat/completions` itself.

## Configuration

Sentient runs with no configuration beyond one provider key. Defaults are FAISS on local disk,
SQLite at `data/state.db`, and auth disabled.

| Variable | Default | Purpose |
| --- | --- | --- |
| `GOOGLE_API_KEY` / `OPENAI_API_KEY` / `HUGGINGFACEHUB_API_TOKEN` | none | At least one is required |
| `LLM_PROVIDER` / `EMBEDDING_PROVIDER` | `auto` | Pin a provider instead of resolving per request |
| `VECTOR_BACKEND` | `faiss` | Set to `qdrant` for hybrid retrieval |
| `DATABASE_URL` | none | Postgres (Neon or Supabase). Falls back to SQLite when unset |
| `NEON_AUTH_JWKS_URL` | none | Blank disables auth and serves a single `default` user |
| `NEON_AUTH_BASE_URL` | none | Written by `neon env pull`; the token `iss` is its origin |
| `SENTIENT_SECRET_KEY` | none | Fernet key enabling the per-user credential vault. Unset ⇒ every `/v1/credentials` route answers 503, which the console renders as a state |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `text` | `LOG_FORMAT=json` emits one JSON object per line for a log shipper |
| `UPLOAD_MAX_BYTES` / `UPLOAD_USER_QUOTA_BYTES` | 25 MiB / 500 MiB | Per-file cap and per-user storage total |

Any `http://localhost:<port>` or `http://127.0.0.1:<port>` origin is allowed by regex, so a Vite
dev server needs no CORS configuration at all. Deployed origins go in `CORS_ALLOW_ORIGINS` **and**
in Neon Auth's trusted-domain list; both are required, and the second is easy to miss because it
fails as `invalid domain` from Neon rather than as a CORS error.

Full reference, including retrieval tuning, Qdrant setup, the credential vault, auth, and
performance measurements: **[CONFIGURATION.md](CONFIGURATION.md)**.

## Architecture

Dependencies point one way, `api → services → adapters → core`, enforced by `import-linter` in CI
rather than left to convention.

```text
src/sentient/
├── core/         # config, errors, concurrency, cache. No I/O, no framework
├── adapters/     # state stores, vector backends, LLM clients, STT, documents
├── services/     # domain logic (NPCBrain, runtime, chat, ingestion). No FastAPI
└── api/          # app factory, composition root, routers, schemas
```

`core/config.py` is the only place environment variables are read. `adapters/state/` and
`adapters/retrieval/` are Protocol seams with swappable implementations (SQLite/Postgres,
FAISS/Qdrant). `apps/console`, `apps/web` and `apps/landing` are separate Node builds outside
the backend gates — `ruff`, `mypy`, `import-linter` and `pytest` are path-scoped to `src/` and
`tests/`, so nothing under `apps/` can turn the Python CI red, and nothing there is covered by
it either. `apps/console` carries its own `lint` / `test` / `build` / `prettier` gates that no
CI job runs yet.

### Tenant partitions

The vector store is partitioned by `user_key`, a short opaque hash of the **user id**, not of the
credential used to authenticate. One person therefore reads and writes one partition whether they
signed in to the console or their game sent an API key, and holding two API keys does not fragment
their lore.

**Upgrading from before 2026-08-22:** partitions written by an earlier build were keyed on the
credential and are now orphaned. There is no automatic migration. Delete `data/projects/` and
re-upload your documents (FAISS), or drop and re-ingest the collection (Qdrant). Do this before
accumulating real data, because the cost only grows.

### Which credential each route accepts

| Route | Bearer JWT | `X-API-Key` | Key in path | No credential |
|---|---|---|---|---|
| `/v1/projects*`, `/v1/threads*`, `/v1/keys*`, `/v1/credentials*` | yes | yes | — | 401 when auth is on |
| `/v1/upload`, `/v1/sources`, `DELETE /v1/sources/{f}` | yes | yes | — | 401 when auth is on |
| `/v1/chat`, `/v1/retrieve` | yes | yes | — | 401 when auth is on |
| `/v1/{api_key}/{project_id}/chat/completions` | — | — | yes | 401 when auth is on |
| `POST /v1/audio/transcriptions` | **provider** key, not a JWT | yes | — | see below |
| `GET /v1/audio/transcriptions/recent` | yes | yes | — | 401 when auth is on |

`POST /v1/audio/transcriptions` is the one route where `Authorization: Bearer` carries a
*provider* credential rather than a Neon Auth JWT. Mantella has a single field for its Whisper key
and forwards it there, so Sentient identity on that route comes from `X-API-Key` only. The
console's voice input cannot reuse that convention.

"Auth is on" means `NEON_AUTH_JWKS_URL` is set. With it unset, every route falls back to the
shared `default` user, which is the single-user local-development mode.

### How in-game conversations become threads

Mantella is a stock OpenAI client: it sends no `session_id`, and it keeps its own
conversation memory in `Documents/My Games/Mantella/data/game/conversations/`. It does
re-send the whole conversation on every turn, so Sentient identifies a thread by hashing
the payload minus the system message and minus the final user turn — the slice that is
exactly what it already stored. Both messages are then appended and the hash advances.

Consequences worth knowing:

- **A summarised conversation starts a new thread.** Once Mantella compacts a long
  exchange into a summary and sends that instead of the transcript, the prefix no longer
  matches. The console shows two threads for what the player experienced as one. This is
  the honest reflection of what happened — the model's context genuinely restarted.
- **A retried turn also starts a new thread**, for the same reason: the previous attempt
  already advanced the stored hash past the prefix the retry arrives with. The alternative
  — letting an empty prefix match an existing thread — would merge two NPCs' opening
  lines, which is the worse failure.
- **Threads are titled from the NPC name when the client sends one**, otherwise from the
  first player line.
- **A client that does send `session_id` gets deterministic identity** and skips the hash
  entirely.
- **All of it runs after the response**, inside `defer()`. It costs nothing on
  time-to-first-token, and it is in-process rather than crash-durable: a process killed
  between the reply and the write loses that turn's transcript, not the reply.

The game path writes this transcript but never reads it back. Mantella carries the
conversation in its own payload; injecting a server-side copy would duplicate the context
and cost tokens on every turn. The transcript is written for the **console** to read.

### Streaming on `POST /v1/chat`

`{"stream": true}` renders the turn as SSE instead of JSON. Omitting the flag returns
exactly the body it always did. The frames are:

1. one `{"object":"sentient.chat.meta","thread_id":"…","sources":[…],"top_k":4}` — the
   `ChatResponse` fields that cannot be appended after the stream, because the client
   renders as it reads,
2. then standard OpenAI `chat.completion.chunk` frames,
3. then `data: [DONE]`.

**Consumers dispatch on `object` and skip anything that is not a `chat.completion.chunk`**,
which is what makes future metadata frames free to add. Check for a top-level `error` key
first, before that filter — see the next section. Read the stream with `fetch` and a
`ReadableStream` reader, not `EventSource`: `EventSource` cannot issue a POST and cannot
set an `Authorization` header.

`stream` requires `project_id`. The projectless path answers through
`NPCBrain.ask_with_context`, which has no streaming twin. Retrieval is awaited before the
response starts, so a reindexing project still answers 409 rather than a broken stream.

### When the provider fails

A provider outage reaches the client as the same OpenAI-shaped payload on both paths, so
one client-side behaviour covers both and a player sees the same sentence either way:

- **Non-streaming** — `502 Bad Gateway` with that payload as the response body.
- **Streaming** — the stream ends with that payload as an SSE frame (below).

```json
{"object":"error","error":{"message":"…","type":"provider_error","code":"…"}}
```

The status is **502, not the upstream's**. Forwarding a provider's `402` verbatim would
claim that *Sentient* requires payment, which is a different and wrong statement; 502 says
"the thing I proxy to failed" and the message carries the upstream's own words. The OpenAI
SDK maps any non-2xx carrying an `error` body to `APIStatusError`, whose `.message` is the
string the player's log shows.

All three `/v1/chat/completions` path shapes behave this way. Before this, the two
Mantella-facing shapes had no exception handling at all, so a dead provider escaped to
Starlette and rendered a bare `text/plain` `Internal Server Error` with nothing in it.

#### Mid-stream, specifically

A streamed turn commits HTTP 200 the moment its first frame flushes, so a provider that
dies after that cannot be reported with a status code. Sentient reports it in-band, as the
last frame before `[DONE]`:

```
data: {"object":"error","error":{"message":"Error code: 402 - payment_required","type":"provider_error","code":"BadRequestError"}}

data: [DONE]
```

The top-level `error` key is the shape the OpenAI SDK already raises `APIError` on, so
Mantella surfaces the outage without a client change. A failed stream never emits a
`finish_reason: "stop"` chunk — claiming a truncated reply ended normally is what made an
outage indistinguishable from an NPC with nothing to say. Whatever tokens did arrive are
kept and persisted; the message is capped at 500 characters.

### When the project is reindexing

Changing a setting that alters the embedding space — `embedding_provider`,
`embedding_model_name` or `mrl_vector_size` — rebuilds the index under a new
`embedding_signature`. While that runs, `/v1/chat`, `/v1/chat/completions` and
`/v1/retrieve` all answer:

```
409 {"detail":"project is reindexing; retrieval temporarily unavailable"}
```

`/v1/retrieve` used to answer `200` with an empty `chunks` list, which is indistinguishable
from a project with no lore in it. The vectors are not missing during the window; every one
of them is written under a signature that did not exist a second earlier, so the filter
matches nothing.

**The 409 window is the rebuild, and nothing longer.** Both edges go through
`RuntimeCache`: a config write invalidates it, so onset is immediate, and since B6 the
reindex handler invalidates it again when the job settles, so clearing is immediate too.

It did not always clear. Until B6, `_reindex_handler` flipped the project back to `active`
without invalidating, and nothing was watching that column — the guard reads `ctx.status`,
and `ctx` comes from a `TTLCache(ttl=60)`. Measured 2026-08-23 and again on 2026-08-25
against Neon: a one-document project finished rebuilding at **t+6.77 s**, read `active` from
that second on, and `/v1/retrieve` kept answering 409 until **t+64.08 s** — 57 s of the API
contradicting its own status field. After the fix the same probe cleared at **t+6.28 s**,
on the same poll that first reported `active`. Evidence:
`docs/superpowers/verification/2026-08-24-B6-F9-error-states.md`.

**A corollary for anything rendering the reindex state:** the project's own `status` is a
much narrower window than the 409. Re-measured 2026-08-24 by polling once a second, a
one-document project read `reindexing_required` at t+1 s and `active` at t+2 s, and an
**empty** project never showed the flip at all. So a UI keyed on `projects.status` will
usually miss the rebuild entirely while a client keyed on the 409 still sees it a minute
later. The console reads the window off the polled document rows instead, and its settings
pane predicts a reindex from the config change rather than from any status at all.

## Rate limits

**Off by default.** A fresh clone behaves exactly like `main`. Turn it on for any deployment a
stranger can reach — until you do, a public origin is an open proxy on your provider bill.

```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_COMPLETIONS_PER_MINUTE=30   # both completions shapes and POST /v1/chat
RATE_LIMIT_UPLOADS_PER_HOUR=60         # POST /v1/upload
RATE_LIMIT_DEFAULT_PER_MINUTE=120      # everything else, including POST /v1/keys
```

A refused request is a **429** with `Retry-After` in whole seconds and the usual `{"detail": …}`
body. `/health` is never throttled — the platform polls it forever, and throttling it would pull
the instance out of the load balancer under exactly the load the limiter exists to survive.

Three things worth knowing before you rely on it:

- **Buckets are per process.** Everything stateful here already is — the object registry, the
  ingest queue, the session locks, the runtime cache — and making the limiter the one component
  that needs Redis would buy a shared store for the cheapest thing in the system. **With N
  replicas the effective limit is N × the number you configure.** That changes when X5 (horizontal
  scale) lands; until then, size the number for the replica count you actually run.
- **Identity is the API key's hash, or the client host when there is no key.** Not the resolved
  user: that needs a database round trip on every request, and verifying a JWT in middleware would
  add a JWKS fetch to the hot path. So a caller who mints ten API keys gets ten buckets, and
  several console users behind one NAT share one. The first gap wants a per-user key cap; the
  second is the safe direction to be wrong, since keying on an unverified token would let an
  attacker mint a fresh bucket per request.
- **It bounds frequency, not spend.** Thirty requests a minute with a 100k-token context on an
  expensive model is still a real bill. `TOKEN_QUOTA_PER_MONTH` is the other half.

### Token quota

The other half, and the one that bounds the bill. `TOKEN_QUOTA_PER_MONTH=0` (the default) means
unlimited; any positive number is a ceiling on `chat_messages.total_tokens` summed across every
project the user owns.

```bash
TOKEN_QUOTA_PER_MONTH=2000000
```

A caller over the ceiling gets a **429** from `/v1/chat` and from all three completions shapes,
raised **before** the provider is called — the request that trips the quota is not the request that
spends the money.

- The window is a **rolling 30 days**, not a calendar month. It recovers on its own; there is no
  reset to remember to run, and no midnight-on-the-31st boundary where two months' budget can be
  spent at once.
- It counts only turns Sentient recorded. Embedding calls during ingestion are bounded by
  `UPLOAD_USER_QUOTA_BYTES` instead.
- `total_tokens` is nullable — a provider that reports no usage contributes zero. The sum
  under-counts rather than guessing.

## Development

```bash
uv run python -m pytest tests/ -v                     # the full suite
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src/sentient/core src/sentient/adapters
uv run lint-imports                                   # layer contract
```

CI runs all five on every push and pull request. Add dependencies with `uv add`; never hand-edit
`uv.lock`.

The console has its own four, run from `apps/console` and **not** wired into CI yet:

```bash
npm run lint            # the layer contract and the fetch-seam ban
npm run test            # vitest
npm run build           # vite build, THEN tsc --noEmit -- routeTree.gen.ts is generated
npx prettier --check .
```

## Deployment

```bash
docker build -f deploy/Dockerfile -t sentient .
docker run -p 8000:8000 --env-file .env -v sentient-data:/app/data sentient
```

`data/` must be a mounted volume. It holds uploads, FAISS partitions, and the SQLite fallback, none
of which survive a redeploy if written inside the container.

<!-- ## License

Not yet chosen. Until a `LICENSE` file lands here, default copyright applies and no usage rights are
granted. -->
