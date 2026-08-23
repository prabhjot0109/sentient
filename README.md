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

The web UI is a separate Vite app:

```bash
cd apps/web && npm install && npm run dev    # http://127.0.0.1:5173
```

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
| `SENTIENT_SECRET_KEY` | none | Fernet key enabling the per-user credential vault |
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
FAISS/Qdrant). `apps/web` and `apps/landing` are separate Node builds outside the backend gates.

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

### When a provider fails mid-stream

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
