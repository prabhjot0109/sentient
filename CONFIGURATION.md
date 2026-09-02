# Configuration reference

Every environment variable is read in one place, `src/sentient/core/config.py`, and nowhere else.
See [README.md](README.md) for setup and the common variables.

```env
GOOGLE_API_KEY=
OPENAI_API_KEY=
HUGGINGFACEHUB_API_TOKEN=
OPENAI_BASE_URL=
LLM_PROVIDER=auto
EMBEDDING_PROVIDER=auto
MODEL_NAME=gemini-2.5-flash
EMBEDDING_MODEL_NAME=models/gemini-embedding-2
OPENAI_TIMEOUT_SECONDS=60
DATA_DIR=data
FAISS_INDEX_PATH=data/faiss_index
RAG_SEARCH_TYPE=similarity
RAG_TOP_K=4
RAG_FETCH_K=12
RAG_MMR_LAMBDA=0.65
RAG_SCORE_THRESHOLD=0.0
RAG_CHUNK_SIZE=900
RAG_CHUNK_OVERLAP=150
NEON_AUTH_BASE_URL=
NEON_AUTH_JWKS_URL=
# NEON_AUTH_ISSUER=   optional; derived from NEON_AUTH_BASE_URL's origin
NEON_AUTH_ALGORITHMS=EdDSA,RS256
```

## Providers

| `LLM_PROVIDER` / `EMBEDDING_PROVIDER` | When it applies | Chat model | Embedding model |
| --- | --- | --- | --- |
| `auto` (default) | Resolved per request. An explicit request key is matched by prefix (`AIza` for Google, `hf_` for HuggingFace, anything else for OpenAI). Otherwise the first of `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `HUGGINGFACEHUB_API_TOKEN` (or `HF_TOKEN`) that is set, in that order. | | |
| `google` | Set explicitly, or resolved when only `GOOGLE_API_KEY` is present | `gemini-2.5-flash` | `models/gemini-embedding-2` |
| `openai` | Set explicitly, or resolved when only `OPENAI_API_KEY` is present | `gpt-4o-mini` | `text-embedding-3-small` |
| `huggingface` | Set explicitly, or the fallback when no provider key is set at all | `Qwen/Qwen2.5-7B-Instruct` (hosted, keyless and rate-limited without a token) | `BAAI/bge-base-en-v1.5` (local, no key) |

`MODEL_NAME` and `EMBEDDING_MODEL_NAME` override the default for whichever provider wins.

A model name belongs to the provider it was written for, which matters in one case. Groq, Cerebras,
and OpenRouter serve chat models only, so when one of them is resolved for embeddings the provider
falls back to local HuggingFace and `EMBEDDING_MODEL_NAME` is ignored in favour of
`BAAI/bge-base-en-v1.5`. A Google or OpenAI model name cannot be loaded from the HuggingFace Hub.
Set `EMBEDDING_PROVIDER` explicitly to pin both halves, which is the usual setup when chat runs on
Groq but embeddings should stay on Google.

`OPENAI_BASE_URL` points the OpenAI provider at a compatible endpoint instead of api.openai.com.
`OPENAI_TIMEOUT_SECONDS` applies to every provider's requests.

## Retrieval and ingestion

| Variable | Default | Meaning |
| --- | --- | --- |
| `RAG_SEARCH_TYPE` | `similarity` | `similarity` ranks by closeness and honours `RAG_SCORE_THRESHOLD`; `mmr` uses maximal marginal relevance to favour diverse chunks |
| `RAG_TOP_K` | `4` | Chunks returned per query |
| `RAG_FETCH_K` | `max(top_k * 3, top_k)` | Candidate pool before MMR re-ranking |
| `RAG_MMR_LAMBDA` | `0.65` | Relevance against diversity, 0 to 1, read only when `RAG_SEARCH_TYPE=mmr` |
| `RAG_SCORE_THRESHOLD` | `0.0` | Drops chunks scoring below this on the grounding path behind `/v1/chat/completions`. `0` keeps everything |
| `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` | `900` / `150` | Chunking during ingestion |
| `RAG_CONDENSE_QUERIES` | `false` | Rewrites pronoun-heavy follow-ups into standalone queries before retrieval. Costs one extra LLM call, gated behind a pronoun heuristic |

Vectors live in a local FAISS index under `FAISS_INDEX_PATH` (default `<DATA_DIR>/faiss_index`).
Uploads and deletions rebuild that index from the files currently under `DATA_DIR` and write a
manifest, keeping retrieval aligned with the actual source documents and embedding configuration.

### Uploads

`POST /v1/upload` stages the file and returns `202` immediately:

```json
{ "status": "processing", "filename": "lore.txt" }
```

The worker writes each document's status as `processing`, then `ready` or `failed`, which callers
poll through `StateStore.list_documents(project_id)`. That worker is in-process and not
crash-durable, so a restart can lose accepted but unfinished jobs. The HTTP layer goes through an
`enqueue_ingest(job)` seam, so a durable queue can replace it without touching callers.

Every upload is validated before a byte reaches the archive, in `services/ingestion.py` rather
than in the route, so every caller of `stage_and_enqueue` is covered:

| Variable | Default | Purpose |
| --- | --- | --- |
| `UPLOAD_MAX_BYTES` | `26214400` (25 MiB) | Per-file cap, enforced while the file is written |
| `UPLOAD_USER_QUOTA_BYTES` | `524288000` (500 MiB) | Per-user total, summed from `documents.size_bytes` |

The filename is reduced to a bare name with both separators stripped regardless of the host OS.
`os.path.basename` alone is not enough: on POSIX it treats a backslash as an ordinary character,
so `..\..\evil.txt` used to pass straight through. Only `.pdf` and `.txt` are accepted, and the
first kibibyte is checked against the claimed extension, because the extension is a claim and not
evidence. The size cap is applied chunk by chunk as the file is staged: `Content-Length` is also
a claim, and a caller that lies about it must not be able to fill the disk before anyone notices.

All four rejections answer `400`. An upload rejected at any point leaves nothing behind in the
staging directory.

### Reindexing

Each project stores an embedding signature derived from its provider, model, and optional MRL vector
size. Changing any of those marks the project as reindexing, purges its project-scoped vectors, and
re-embeds every registered source in the background. Retrieval returns `409` with
`project is reindexing; retrieval temporarily unavailable` until the worker finishes, after which
the project returns to `active`. A failed reindex leaves the project guarded rather than serving
stale vectors.

### Scanned PDF OCR

PDFs with no selectable text are read with OCR. Pages that come back empty from normal extraction
are rendered with PyMuPDF and passed through Tesseract. The `pymupdf`, `pytesseract`, and `pillow`
packages arrive with `uv sync`, but the Tesseract binary installs separately:

- Windows: the [UB-Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki). If it is not on
  your `PATH`, set `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`.
- macOS: `brew install tesseract`. Linux: `apt install tesseract-ocr`.

Without Tesseract, scanned PDFs ingest as empty and log a warning. Text PDFs are unaffected.

## Vector backend

Storage sits behind an async `VectorBackend` protocol, so the store is swappable and the whole
retrieval chain stays non-blocking. CPU-bound work is offloaded off the event loop.

| Variable | Default | Meaning |
| --- | --- | --- |
| `VECTOR_BACKEND` | `faiss` | `faiss` for local disk, `qdrant` for server-side hybrid retrieval |
| `QDRANT_URL` / `QDRANT_API_KEY` | empty | Qdrant Cloud cluster URL and API key |
| `QDRANT_PREFER_GRPC` | `false` | gRPC instead of HTTP, recommended for Cloud |
| `QDRANT_COLLECTION` | `sentient_lore` | Collection name |
| `RAG_SPARSE_MODEL` | `Qdrant/bm25` | Local FastEmbed sparse model for hybrid retrieval |
| `RAG_HYBRID` | `false` | Enable hybrid dense and sparse retrieval |

FAISS is the default and needs no configuration. Setting `VECTOR_BACKEND=qdrant` buys three things.

**Hybrid retrieval fused server-side.** Provider embeddings supply the dense vector and a local
FastEmbed BM25 model supplies the sparse one. Qdrant runs both searches and fuses them with
Reciprocal Rank Fusion, so an exact keyword such as an item, skill, or place name still ranks even
when pure dense similarity would miss it. No Python-side merge, no cross-encoder.

**Cheaper vectors.** The collection is created with scalar `INT8` quantization, roughly 4x smaller
and kept in RAM, over a tuned HNSW graph (`m=16`, `ef_construct=100`).

**Tenant isolation during traversal.** Project-aware reads apply a server-side `Filter` on
`user_key` and `project_id` while the graph is walked, rather than filtering afterward. FAISS
achieves the same isolation with a separate on-disk index per user and project scope. Qdrant
write-side request tagging is not finished, so use FAISS if you need end-to-end multi-project
ingestion isolation today.

`langchain-qdrant`'s store is driven synchronously, but every hot-path call is wrapped in
`asyncio.to_thread`, matching the FAISS model. For Qdrant Cloud set `QDRANT_URL`, `QDRANT_API_KEY`,
and `QDRANT_PREFER_GRPC=true`. The collection is created idempotently on first write.

## Relational state

Users, API keys, projects, per-project configs (including each project's single editable
`persona_prompt`), chat threads, and the document registry sit behind an async `StateStore` protocol
in `src/sentient/adapters/state/`, selected by `DB_BACKEND`:

| `DB_BACKEND` | Store | Connection source |
| --- | --- | --- |
| unset (default) | Postgres when `DATABASE_URL` is set, otherwise SQLite | `DATABASE_URL` |
| `neon` | `PostgresStateStore` (asyncpg) | `DATABASE_URL` |
| `supabase` | `PostgresStateStore` (asyncpg) | `SUPABASE_DB_URL` or `DATABASE_URL` |
| `sqlite` | `SQLiteStateStore` | `${DATA_DIR}/state.db` |

Neon and Supabase are both Postgres, so they share one asyncpg implementation and differ only in the
DSN. The schema ships as `migrations/0001_runtime_schema.sql`, applied idempotently the first time a
pool opens, and is mirrored by the SQLite store's `_init()`. With no `DATABASE_URL` set, state goes
to SQLite at `data/state.db` and needs no setup.

### Chat history

`POST /v1/chat` optionally takes `project_id` and `thread_id`. Supplying a project starts or
continues a durable thread, returns its `thread_id`, and folds the last `history_window` messages
(20 by default, set per project) into the next generation. Both writes for a turn are deferred past
the response, so reply latency never includes them. `GET /v1/projects/{project_id}/threads` backs a
sidebar and `GET /v1/threads/{thread_id}/messages?limit=50` returns chronological history. Every
thread, message, and credential read is filtered by owning user, so another user's ids return `404`
rather than someone else's data.

Server-side memory is web-only by design. Game completions stay driven by the payload history and
never read stored messages. A game client that wants its sessions listed in the sidebar can send two
optional non-OpenAI fields alongside the standard body, `session_id` (stable per in-game
conversation) and `npc_name`, and the project game route records a write-only thread for them.
Clients that omit both are unaffected.

## Credential vault

Set `SENTIENT_SECRET_KEY` to a Fernet key to let users manage their own provider keys:

```bash
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`POST /v1/credentials` takes a provider (`google`, `openai`, `huggingface`, `groq`, `cerebras`,
`openrouter`) and a key. The database receives Fernet ciphertext only, and listings return a
last-four-character hint, so the raw key is never stored, logged, or returned again. Without
`SENTIENT_SECRET_KEY`, credential routes return `503` and environment keys keep working.

Keys resolve per provider, after the project config is applied, so the chat model and the embedding
model each get the key belonging to whichever provider that project actually chose. For each, the
order is:

1. an explicit provider key in the request URL, when its prefix says it belongs to that provider,
2. the user's stored credential for that provider,
3. the provider's environment variable (`GOOGLE_API_KEY`, `OPENAI_API_KEY`, and so on).

Resolved keys are hashed into `config_signature`, so swapping a credential yields fresh clients on
its own. Credential writes also invalidate the runtime cache for every project the user owns, which
makes the change land on the next turn instead of after the 60 second TTL. A credential that fails
to decrypt, usually a rotated or malformed `SENTIENT_SECRET_KEY`, logs a warning and falls back to
the environment key, so a bad secret degrades instead of taking chats down.

The threat model, stated plainly: Fernet protects keys at rest, meaning a database dump is not a key
leak. It does nothing against a compromised running process, which has to hold the plaintext to call
the provider at all. That is the right trade-off for a self-hosted service and not a claim of
end-to-end secrecy.

## Authentication

Every request resolves to a `user_id` one of two ways, and auth is enforced only once configured.

Web clients send a Neon Auth JWT as `Authorization: Bearer <jwt>`, verified against the JWKS URL for
signature, issuer, and an algorithm allowlist. The authenticated user is the token's `sub` claim.

Game clients put a `sk-sent-...` API key in the request path. Keys are minted with `POST /v1/keys`,
shown once, and stored only as a `sha256` hash, so the raw key is never persisted or logged.
Validation is a hash lookup and revoked keys are rejected immediately. This path works whether or
not JWT auth is enabled.

Leaving `NEON_AUTH_JWKS_URL` blank disables auth entirely and serves a single `default` user, which
is why a local SQLite clone needs no auth configuration.

A warm `IdentityCache`, keyed by token or key hash with a TTL, memoizes the resolved
`(user_id, user_key)`. A live session touches the database at most once per key per TTL window, and
steady-state turns cost a hash and a dict lookup, which keeps auth off the model-call critical path.
Configure with `NEON_AUTH_BASE_URL`, `NEON_AUTH_JWKS_URL` and `NEON_AUTH_ALGORITHMS`; both URLs
come from `neon env pull` and are branch-specific. The `iss` claim tokens are checked against is
derived from `NEON_AUTH_BASE_URL`'s **origin** (scheme and host, no path). That is measured, not
assumed: Better Auth documents the issuer as defaulting to the full base URL, but Neon's tokens
carry the origin alone, and `jwt.decode` compares `iss` as an exact string, so the difference is
the difference between every token verifying and every token being rejected. Set
`NEON_AUTH_ISSUER` only to override a measured mismatch.

## Speech-to-text proxy

`POST /v1/audio/transcriptions` is an OpenAI-compatible Whisper proxy that exists to answer one
question Mantella cannot. When the mod reports `Could not detect speech from mic input`, was the
microphone dead, was the level too low, or did the model genuinely hear nothing? Those need opposite
fixes, so every payload is measured for duration, sample rate, RMS, peak, and clipping, and the
verdict is printed next to the transcription.

It is optional and off by default. Nothing calls it unless you point Mantella's `whisper_url` at it
with `external_whisper_service = True`.

Credentials resolve in order: a forwarded `Authorization: Bearer` key, then the user's stored
credential for that provider (Groq before OpenAI), then the `GROQ_API_KEY` or `OPENAI_API_KEY`
environment floor. With no credential anywhere the request is rejected with `400` before any
upstream call. Only the source of a key is ever logged.

This is the one route where `Authorization: Bearer` carries a provider key rather than a Neon Auth
JWT, because Mantella has a single field for its Whisper credential. Sentient identity comes from
`X-API-Key` here, and is optional.

Groq serves only the `whisper-large-v3` family and OpenAI only `whisper-1`, so a mismatched model
name is corrected rather than forwarded into a `400`.

Whisper reliably invents stock phrases such as "Thank you." out of silence. When the waveform
provably carries no speech (`SILENT` or `VERY_QUIET`), the text is dropped and `""` returned, so
Mantella replays its own "could not detect speech" cue instead of making the NPC answer a line the
player never spoke. Healthy audio is never discarded, and an unparseable payload degrades to
`UNREADABLE`, so diagnostics never cost you a transcription.

## CORS

Any `http://localhost:<port>` or `http://127.0.0.1:<port>` origin is allowed by a regex in
`api/app.py`, so a Vite dev server works on whatever port it lands on and no configuration is
needed for local development. `tests/test_cors.py` pins that through a real preflight.

Deployed origins go in `CORS_ALLOW_ORIGINS` (comma-separated) **and** in Neon Auth's
trusted-domain list (`neon neon-auth domain add <origin>`). Both are required, and the second is
easy to miss because the failure surfaces as `invalid domain` from Neon rather than as a CORS
error in the browser. FastAPI honours the explicit list and the regex together, so adding a
production origin does not cost the dev-port coverage.

## Logging

| Variable | Default | Purpose |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | Any stdlib level name: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FORMAT` | `text` | `json` emits one JSON object per line. Anything else is text |

Every record carries the request's `user_key`, and `project_id` and `thread_id` once they are
known, bound once per request in `deps.resolve_caller` and carried by a `ContextVar`. Deferred
post-turn work inherits those fields, because an asyncio task copies the context it was created
in, so the transcript write logs under the turn that scheduled it.

`user_key` is an opaque hash of the user id, which is exactly why it is the field that identifies
a tenant in the logs. No provider key, `sk-sent-` key or JWT is ever logged, and the STT path logs
only *where* a credential came from.

The server contains no `print()` calls, and `tests/test_logging.py` fails the suite if one
reappears. `cli.py` is the deliberate exception: a console script's stdout is its user interface,
not a log.

## Error tracking

| Variable | Default | Purpose |
| --- | --- | --- |
| `SENTRY_DSN` | *(empty)* | Empty means off, and off means no client is constructed at all |
| `SENTRY_ENVIRONMENT` | `development` | The name an on-call reader sees on the event |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.0` | Performance tracing. Langfuse already carries the spans |

Off by default: a fresh clone reports to nobody. `sentry-sdk` is in the optional `observability`
dependency group, so `uv sync` does not install it — a group that installs itself has not made an
integration optional, only quiet. Turn it on locally with `uv sync --group observability`; the
deployed image asks for it explicitly (`deploy/Dockerfile`). With the DSN set and the package
absent the app logs one warning at startup and runs untracked, because an observability tool must
never be a startup dependency of the thing it observes.

**The game route carries the API key in the URL path**, so an error tracker with default settings
would copy other people's credentials into a third-party SaaS. `core/scrubbing.py` is a `before_send`
hook that replaces exactly that one path segment and keeps the rest, so an event is still findable:

```
/v1/sk-sent-abc123/8d2f…/chat/completions  ->  /v1/[redacted]/8d2f…/chat/completions
```

`X-API-Key`, `Authorization` and `Cookie` are redacted the same way, and `send_default_pii` is off
explicitly rather than by relying on the SDK default. `SECURITY.md` accepts the key-in-path for logs
the operator controls; this is the boundary where that stops being true.

## Performance notes

Measured against a live Skyrim session, in descending order of impact. The first item outweighs
every server-side optimisation below it.

**Never point a client at `http://localhost:8000` on Windows. Use `http://127.0.0.1:8000`.** Uvicorn
binds IPv4 only and Windows resolves `localhost` to `::1` first, so every connection stalls on a
refused IPv6 attempt before falling back. Measured at 208 ms through `localhost` against 0.8 ms
through `127.0.0.1`, paid per request before any work starts. End-to-end streaming TTFT for one NPC
line went from roughly 3200 ms to 780 ms on that change alone. It never appears in Sentient's own
logs, because the server never sees the wasted time, which is why it went unnoticed for so long.

**Reasoning models are a TTFT trap.** `openai/gpt-oss-20b` measured 583 ms to first token against
146 ms for `llama-3.1-8b-instant`, because it emits a full chain of thought before the first spoken
word. For dialogue, time to first token is the perceived latency.

**Query embedding is the retrieval cost, not the search.** Local `BAAI/bge-base-en-v1.5` runs about
48 ms; the Google round trip it replaced was about 511 ms; the FAISS search they feed takes 0.2 ms.
Optimising the vector search would have meant optimising 0.4% of the work.

**The embedding model takes 7 to 9 seconds to load**, so `_warm_grounding_path()` warms it at
startup and the player's opening line does not pay for it. Changing `EMBEDDING_MODEL_NAME` re-embeds
the whole corpus on next start, a one-off cost of roughly 110 seconds for 96 chunks locally.

**Reusing the STT client cut transcription from 389 ms to 185 ms.** The SDK client owns an HTTP
connection pool, and rebuilding it per utterance pays a fresh TCP and TLS handshake on the critical
path between the player finishing a sentence and the NPC answering.

**Mic diagnostics cost 1.2 ms** on a 3 second 16 kHz capture, which is free at this scale.

## Deployment

```bash
docker build -f deploy/Dockerfile -t sentient .
docker run -p 8000:8000 --env-file .env -v sentient-data:/app/data sentient
```

Two deliberate choices in the image are worth knowing about. `migrations/` ships inside it, because
`PostgresStateStore` applies every `.sql` file in that directory the first time it opens a pool.
Drop the directory and the pool still opens, zero migrations apply, and the first real query fails
on a missing relation. `data/`, by contrast, is not baked in. It holds per-tenant runtime state
(uploads, FAISS partitions, the SQLite fallback), so it belongs on a mounted volume. Baking one
deployment's lore into the image is wrong for a multi-project runtime, and any write inside the
container would vanish on the next deploy.

Set `CORS_ALLOW_ORIGINS` to your frontend origins, comma-separated. Local Vite ports stay allowed
either way, so the same value works in development and production.
