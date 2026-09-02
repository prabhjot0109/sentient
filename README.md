<div align="center">

# Sentient

**Give a game's NPCs a memory of its world.**

Sentient is a retrieval-augmented dialogue backend. Upload the documents that define a game world,
and it serves an OpenAI-compatible `/v1/chat/completions` endpoint whose answers are grounded in
that lore instead of in whatever the base model happens to know.

[![CI](https://github.com/prabhjot0109/sentient/actions/workflows/ci.yml/badge.svg)](https://github.com/prabhjot0109/sentient/actions/workflows/ci.yml)
[![Console](https://github.com/prabhjot0109/sentient/actions/workflows/console.yml/badge.svg)](https://github.com/prabhjot0109/sentient/actions/workflows/console.yml)
[![Landing](https://github.com/prabhjot0109/sentient/actions/workflows/landing.yml/badge.svg)](https://github.com/prabhjot0109/sentient/actions/workflows/landing.yml)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)

[Live console](https://sentient-console.vercel.app) ·
[Site](https://sentient-npc.vercel.app) ·
[API docs](https://sentient-api-54r2.onrender.com/docs) ·
[Configuration](CONFIGURATION.md) ·
[Mantella setup](MANTELLA.md) ·
[Self-hosting](SELFHOST.md) ·
[Deployment](DEPLOY.md) ·
[Security](SECURITY.md)

</div>

---

## What it is

An NPC that runs on a stock language model answers from the model's training data. Ask it about a
faction you invented last week and it will invent one back. Sentient sits between the game and the
provider: it retrieves the passages of your own documents that bear on what the player just said,
puts them behind the character's persona, and streams the reply back over the wire shape the game
already speaks.

It exists because [Mantella](https://www.nexusmods.com/skyrimspecialedition/mods/98631) — the
Skyrim mod that gives NPCs live voiced conversation — accepts any OpenAI-compatible endpoint as its
language-model backend. Point it at Sentient instead of at OpenAI and the same NPCs start answering
from your lore. Nothing about the design is Skyrim-specific; anything that speaks the OpenAI chat
API can use it.

```
                    ┌──────────────────────────────────────────────┐
  Player speaks     │  Sentient                                    │
        │           │                                              │
        ▼           │   retrieve ──► rank ──► persona ──► provider │
  Mantella ────────►│      ▲                                  │    │
   (or any          │      │                                  ▼    │
    OpenAI client)  │   your lore, per project           SSE stream │
        ▲           │   (FAISS or Qdrant)                      │   │
        └───────────┴──────────────────────────────────────────┘   │
                        NPC answers in character, from your world
```

**Status.** Running in production since 2026-09-01 on Render, Neon Postgres and Qdrant Cloud. The
full loop is proven end to end on the live deployment: a real turn retrieves from an uploaded PDF
and the NPC answers from it. The free-tier instance is 0.15 CPU, which is the honest constraint
behind every latency number quoted below.

## Highlights

- **Drop-in OpenAI compatibility.** Chat completions with SSE streaming. Existing clients need a
  new base URL and nothing else.
- **Multi-project by design.** One deployment, many users, many game worlds. Each project owns its
  config, its single editable persona, its documents and its chat threads, and the vector store is
  partitioned so nothing crosses between them. Five persona presets ship — `skyrim`, `fallout4`,
  `fantasy`, `scifi`, `cyberpunk` — and each is a starting point you edit, not a constraint.
- **Six providers, resolved per request.** Google, OpenAI, HuggingFace, Groq, Cerebras, OpenRouter.
- **Two retrieval backends behind one seam.** FAISS on local disk by default; Qdrant for hybrid
  dense-plus-sparse retrieval with server-side tenant filters.
- **Bring your own keys.** Per-user provider credentials, encrypted at rest with Fernet, with a
  no-downtime rotation path.
- **PDF and TXT ingestion, including scanned PDFs** through OCR.
- **Speech-to-text that measures the waveform**, so a failed transcription can tell you whether the
  microphone was dead or the model heard nothing — and text a model invented from silence never
  reaches an NPC.

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/prabhjot0109/sentient.git
cd sentient
uv sync
cp .env.example .env          # add at least one provider key
uv run uvicorn sentient.api.app:app --reload
```

Interactive API docs are then at <http://127.0.0.1:8000/docs>. With no further configuration you
get FAISS on local disk, SQLite at `data/state.db`, and authentication disabled — a single-user
local install.

Upload a document and talk to it:

```bash
curl -F "file=@lore.pdf" http://127.0.0.1:8000/v1/upload

curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"sentient","messages":[{"role":"user","content":"Who rules Skyrim?"}]}'
```

> **Use `127.0.0.1`, never `localhost`.** On Windows that one choice costs 208 ms per request,
> because uvicorn binds IPv4 only and Windows resolves `localhost` to `::1` first. The wait is
> invisible in server-side logs. See [performance notes](CONFIGURATION.md#performance-notes).

<details>
<summary><b>Why <code>uv sync</code> installs torch, and how to skip it</b></summary>

`uv sync` includes the `local-embeddings` group, which carries `sentence-transformers` for
`EMBEDDING_PROVIDER=huggingface` — the local-model provider an unset `EMBEDDING_PROVIDER` falls
back to. It is the only thing here that needs torch, and torch costs 158 MB of resident memory and
17 seconds of startup. A deployment using a hosted embedding provider omits it:

```bash
uv sync --no-default-groups     # what deploy/Dockerfile does: 305 MB / 20.0 s → 147 MB / 3.3 s
```

Selecting `huggingface` embeddings without the group raises an error naming both ways out.

</details>

## Connecting Mantella

Mint an API key, then set Mantella's `baseUrl` to:

```
http://127.0.0.1:8000/v1/<api_key>/<project_id>
```

Mantella appends `/chat/completions` itself, so the URL you paste must not include it. The console
prints the exact string for each key you mint, derived from wherever the API actually lives.

For the microphone, point Mantella's **Whisper URL** at `/v1/audio/transcriptions` with *External
Whisper Service* enabled. Mantella keeps doing its own text-to-speech and should: it has real
per-character Skyrim voice models and generates LipGen facial animation from the audio locally.
Sentient serves no TTS.

`config/config.ini` in this repository is **Mantella's** config, checked in as reference wiring
only. Sentient never reads it; Mantella reads `Documents/My Games/Mantella/config.ini`.

**[MANTELLA.md](MANTELLA.md) is the full walkthrough**, written for people who install mods rather
than for backend engineers: the exact fields, the microphone, and troubleshooting organised by
symptom with the measurement behind each cause.

## The console

A web console for everything the API can do, so onboarding does not require `curl`.

```bash
cd apps/console && npm install && npm run dev    # http://localhost:5175
```

From it you can create a project per game, mint an API key and copy the Mantella base URL, upload
lore and watch it index, read and hold conversations, change the model and retrieval settings, edit
the project's persona, and store your own provider keys.

> **`localhost` for the console, `127.0.0.1` for the backend, and the two do not conflict** — they
> are different hops. Neon Auth trusts the hostname `localhost` and rejects
> `http://127.0.0.1:<port>` with `INVALID_ORIGIN` before it validates anything, so the console is
> browsed at `localhost` while its `VITE_API_BASE_URL` stays `127.0.0.1:8000`.

`apps/landing` is the marketing site that links to it. Both are separate Vite builds with their own
lint, test and build gates in their own path-filtered GitHub Actions workflow.

## Configuration

Sentient runs with no configuration beyond one provider key. Every knob has a default that
preserves the single-user local behaviour.

| Variable | Default | Purpose |
| --- | --- | --- |
| `GOOGLE_API_KEY` / `OPENAI_API_KEY` / `HUGGINGFACEHUB_API_TOKEN` | none | At least one is required |
| `LLM_PROVIDER` / `EMBEDDING_PROVIDER` | `auto` | Pin a provider instead of resolving per request |
| `VECTOR_BACKEND` | `faiss` | Set to `qdrant` for hybrid retrieval |
| `DATABASE_URL` | none | Postgres (Neon or Supabase). Falls back to SQLite when unset |
| `NEON_AUTH_JWKS_URL` | none | Blank disables auth and serves a single `default` user |
| `NEON_AUTH_BASE_URL` | none | Written by `neon env pull`; the token `iss` is its origin |
| `SENTIENT_SECRET_KEY` | none | Fernet key enabling the per-user credential vault |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `text` | `LOG_FORMAT=json` emits one JSON object per line |
| `UPLOAD_MAX_BYTES` / `UPLOAD_USER_QUOTA_BYTES` | 25 MiB / 500 MiB | Per-file cap and per-user total |
| `RATE_LIMIT_ENABLED` | `false` | Per-key request limits. **Turn on for any public origin** |
| `TOKEN_QUOTA_PER_MONTH` | `0` | `0` is unlimited. Bounds spend, where the rate limit bounds frequency |
| `STT_PROVIDER` | none | `groq`, `openai` or `custom`. Unset infers from whichever credential resolves first |
| `SENTRY_DSN` | none | Error tracking. Empty means no client is constructed at all |
| `LANGFUSE_ENABLED` | `false` | Tracing: retrieval, provider latency, token counts and cost per turn |

**Full reference — retrieval tuning, Qdrant setup, the credential vault, authentication, CORS and
performance measurements: [CONFIGURATION.md](CONFIGURATION.md).**

Any `http://localhost:<port>` or `http://127.0.0.1:<port>` origin is allowed by regex, so a Vite
dev server needs no CORS configuration. Deployed origins go in `CORS_ALLOW_ORIGINS` **and** in Neon
Auth's trusted-domain list. Both are required, and the second is easy to miss because it fails as
`invalid domain` from Neon rather than as a CORS error.

### The credential vault

Set `SENTIENT_SECRET_KEY` to let users store their own provider keys:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Without it every credential route answers `503 credential vault is not configured` — including the
listing, so the console can say the vault is unconfigured rather than that you have no keys, since
the two lead to opposite next actions.

**Changing that key does not error.** It silently stops every stored credential from decrypting and
falls back to the environment key, so each user's own key quietly stops being used and the first
symptom is a bill. Rotate it properly:

<details>
<summary><b>Rotating <code>SENTIENT_SECRET_KEY</code> with no downtime</b></summary>

`SENTIENT_SECRET_KEY_OLD` is a comma-separated list of retired keys accepted for **decryption
only**; new writes always use `SENTIENT_SECRET_KEY`.

```bash
# 1. Deploy with both keys. Everything still decrypts; new writes use the new key.
SENTIENT_SECRET_KEY=<new>
SENTIENT_SECRET_KEY_OLD=<old>

# 2. Re-encrypt every stored row under the new key.
uv run sentient rotate-secret

# 3. Deploy again with SENTIENT_SECRET_KEY_OLD removed.
```

`sentient rotate-secret` takes **no key arguments** — both come from the environment. A vault key
typed on a command line lands in shell history and in every process listing on the box, which is a
worse outcome than the problem the command exists to fix.

It refuses to run when `SENTIENT_SECRET_KEY_OLD` is unset (exit **1**): the dangerous order is
changing the key and rotating *before* setting the old one, where every row fails and a long list
of failures reads far too much like "already done". A row that decrypts under neither key is named
by user and provider and skipped rather than aborting the run (exit **2**) — those are the
credentials their owners must re-enter. Exit **0** means it is safe to do step 3.

Skip the procedure and every stored credential becomes undecryptable. There is no recovery; each
user must re-enter their provider key.

</details>

## Architecture

Dependencies point one way, `api → services → adapters → core`, enforced by `import-linter` in CI
rather than left to convention. A violation is an architectural regression, so the code moves
rather than the contract weakening.

```text
src/sentient/
├── core/         # config, errors, concurrency, cache, crypto. No I/O, no framework
├── adapters/     # state stores, vector backends, LLM clients, STT, documents
├── services/     # domain logic (NPCBrain, runtime, chat, ingestion). No FastAPI
└── api/          # app factory, composition root, nine routers, schemas
```

`core/config.py` is the only place environment variables are read. `adapters/state/` and
`adapters/retrieval/` are Protocol seams with swappable implementations — SQLite or Postgres, FAISS
or Qdrant — selected by configuration rather than by import.

`apps/console` and `apps/landing` are separate Node builds deliberately outside the backend gates:
`ruff`, `mypy`, `import-linter` and `pytest` are path-scoped to `src/` and `tests/`, so nothing
under `apps/` can turn the Python CI red. Each runs its own gates in its own workflow instead, so a
console failure names itself rather than reading as a backend failure.

<details>
<summary><b>Tenant partitions, and one upgrade note</b></summary>

The vector store is partitioned by `user_key`, a short opaque hash of the **user id**, not of the
credential used to authenticate. One person therefore reads and writes one partition whether they
signed in to the console or their game sent an API key, and holding two API keys does not fragment
their lore.

**Upgrading from before 2026-08-22:** partitions written by an earlier build were keyed on the
credential and are now orphaned. There is no automatic migration. Delete `data/projects/` and
re-upload your documents (FAISS), or drop and re-ingest the collection (Qdrant). Do this before
accumulating real data, because the cost only grows.

</details>

<details>
<summary><b>Which credential each route accepts</b></summary>

| Route | Bearer JWT | `X-API-Key` | Key in path | No credential |
|---|---|---|---|---|
| `/v1/projects*`, `/v1/threads*`, `/v1/keys*`, `/v1/credentials*` | yes | yes | — | 401 when auth is on |
| `/v1/upload`, `/v1/sources`, `DELETE /v1/sources/{f}` | yes | yes | — | 401 when auth is on |
| `/v1/chat`, `/v1/retrieve` | yes | yes | — | 401 when auth is on |
| `/v1/{api_key}/{project_id}/chat/completions` | — | — | yes | 401 when auth is on |
| `POST /v1/audio/transcriptions` | JWT **or** a provider key | yes | — | resolves the env floor |
| `GET /v1/audio/transcriptions/recent` | yes | yes | — | 401 when auth is on |

`POST /v1/audio/transcriptions` is the one route where `Authorization: Bearer` can carry a
*provider* credential rather than an identity token. Mantella has a single field for its Whisper
key and forwards it there; the console has no provider key and sends its ordinary bearer token.
Both are accepted, told apart by **shape** — a token with JWT shape (two dots, `eyJ` prefix) is
identity, anything else is a Whisper credential to forward upstream. Deciding by shape rather than
by attempting a verification keeps a JWKS round trip off the critical path of every spoken line.

Sending no credential at all is valid there and resolves the provider key from the environment
floor. That is the single-user local mode, which is why identity is *resolved* on that route rather
than required.

"Auth is on" means `NEON_AUTH_JWKS_URL` is set. With it unset, every route falls back to the shared
`default` user. Note that ownership failures on `/v1/upload`, `DELETE /v1/sources/{f}` and both
game-path routes answer **403 rather than 404**: they resolve through a context that confirms
existence where the management routes deliberately mask it.

</details>

<details>
<summary><b>Speech to text, and the three backends</b></summary>

One endpoint serves both surfaces: Mantella's microphone and the console's push-to-talk button.
Every utterance is measured — duration, RMS, peak, clipping — and text the model invented from
silence is discarded before it can reach an NPC. Whisper reliably hallucinates stock phrases when
handed a dead capture, and an NPC answering a line the player never spoke is worse than an NPC
staying quiet.

Three backends, selected by name rather than inferred from a key prefix:

```bash
STT_PROVIDER=groq        # whisper-large-v3-turbo. Fastest and cheapest for Whisper.
STT_PROVIDER=openai      # whisper-1
STT_PROVIDER=custom      # any OpenAI-compatible server, via STT_BASE_URL
```

`STT_PROVIDER` is **authoritative**: if the named provider has no usable credential the request is
refused rather than quietly billed to a different account. Leaving it unset keeps the historical
behaviour of walking Groq then OpenAI, taking your vault key before the server's env key for *each*
provider — so a stored OpenAI key does not beat the server's Groq key.

`custom` is the lowest-latency option and needs no API key, because whisper.cpp in server mode
authenticates nothing. A transcription server on the same machine removes the provider network hop
from the critical path of every spoken line:

```bash
STT_BASE_URL=http://127.0.0.1:8080/v1
```

Adding another backend is a registry entry in `adapters/stt/client.py` plus a base URL. Every
service worth adding serves OpenAI-shaped `/v1/audio/transcriptions`, so no new SDK is involved.

</details>

<details>
<summary><b>How in-game conversations become threads</b></summary>

Mantella is a stock OpenAI client: it sends no `session_id`, and it keeps its own conversation
memory on disk. It does re-send the whole conversation on every turn, so Sentient identifies a
thread by hashing the payload minus the system message and minus the final user turn — the slice
that is exactly what it already stored. Both messages are then appended and the hash advances.

- **A summarised conversation starts a new thread.** Once Mantella compacts a long exchange into a
  summary and sends that instead of the transcript, the prefix no longer matches. The console shows
  two threads for what the player experienced as one. That is the honest reflection of what
  happened; the model's context genuinely restarted.
- **A retried turn also starts a new thread**, for the same reason. The alternative — letting an
  empty prefix match an existing thread — would merge two NPCs' opening lines, which is worse.
- **Threads are titled from the NPC name** when the client sends one, otherwise from the first
  player line.
- **A client that does send `session_id` gets deterministic identity** and skips the hash entirely.
- **All of it runs after the response**, inside `defer()`. It costs nothing on time-to-first-token,
  and it is in-process rather than crash-durable: a process killed between the reply and the write
  loses that turn's transcript, not the reply.

The game path writes this transcript but never reads it back. Mantella carries the conversation in
its own payload; injecting a server-side copy would duplicate the context and cost tokens every
turn. The transcript is written for the **console** to read.

</details>

<details>
<summary><b>Streaming on <code>POST /v1/chat</code></b></summary>

`{"stream": true}` renders the turn as SSE instead of JSON. Omitting the flag returns exactly the
body it always did. The frames are:

1. one `{"object":"sentient.chat.meta","thread_id":"…","sources":[…],"retrieval_error":null,"top_k":4}`
   — the `ChatResponse` fields that cannot be appended after the stream, because the client renders
   as it reads. `retrieval_error` is set when the lore lookup itself **failed**, which an empty
   `sources` alone cannot say: the reply then came from the persona with no lore behind it, and a
   client rendering the two identically reports a broken retrieval backend as an NPC with nothing
   to say,
2. then standard OpenAI `chat.completion.chunk` frames,
3. then `data: [DONE]`.

**Consumers dispatch on `object` and skip anything that is not a `chat.completion.chunk`**, which
is what makes future metadata frames free to add. Check for a top-level `error` key first. Read the
stream with `fetch` and a `ReadableStream` reader, not `EventSource`: `EventSource` cannot issue a
POST and cannot set an `Authorization` header.

`stream` requires `project_id`. The projectless path answers through `NPCBrain.ask_with_context`,
which has no streaming twin. Retrieval is awaited before the response starts, so a reindexing
project answers 409 rather than a broken stream.

</details>

<details>
<summary><b>What a client sees when the provider fails</b></summary>

A provider outage reaches the client as the same OpenAI-shaped payload on both paths, so one
client-side behaviour covers both and a player sees the same sentence either way.

```json
{"object":"error","error":{"message":"…","type":"provider_error","code":"…"}}
```

- **Non-streaming** — `502 Bad Gateway` with that payload as the body.
- **Streaming** — the stream ends with that payload as the last SSE frame before `[DONE]`.

The status is **502, not the upstream's**. Forwarding a provider's `402` verbatim would claim that
*Sentient* requires payment, which is a different and wrong statement; 502 says "the thing I proxy
to failed" and the message carries the upstream's own words. The OpenAI SDK maps any non-2xx
carrying an `error` body to `APIStatusError`, whose `.message` is the string the player's log shows.

A streamed turn commits HTTP 200 the moment its first frame flushes, so a provider that dies after
that cannot be reported with a status code — hence the in-band frame. A failed stream never emits a
`finish_reason: "stop"` chunk, because claiming a truncated reply ended normally is what made an
outage indistinguishable from an NPC with nothing to say. Whatever tokens did arrive are kept and
persisted; the message is capped at 500 characters.

</details>

<details>
<summary><b>What happens while a project is reindexing</b></summary>

Changing a setting that alters the embedding space — `embedding_provider`, `embedding_model_name`
or `mrl_vector_size` — rebuilds the index under a new `embedding_signature`. While that runs,
`/v1/chat`, `/v1/chat/completions` and `/v1/retrieve` all answer:

```
409 {"detail":"project is reindexing; retrieval temporarily unavailable"}
```

`/v1/retrieve` used to answer `200` with an empty `chunks` list, which is indistinguishable from a
project with no lore in it. The vectors are not missing during the window; every one of them is
written under a signature that did not exist a second earlier, so the filter matches nothing.

**The 409 window is the rebuild and nothing longer.** Both edges go through `RuntimeCache`: a
config write invalidates it, so onset is immediate, and the reindex handler invalidates it again
when the job settles, so clearing is immediate too. It did not always: measured against Neon, a
one-document project finished rebuilding at **t+6.77 s**, read `active` from that second on, and
`/v1/retrieve` kept answering 409 until **t+64.08 s** — 57 seconds of the API contradicting its own
status field. After the fix the same probe cleared at **t+6.28 s**, on the same poll that first
reported `active`.

**A corollary for anything rendering the reindex state:** the project's own `status` is a much
narrower window than the 409. Polling once a second, a one-document project read
`reindexing_required` at t+1 s and `active` at t+2 s, and an **empty** project never showed the flip
at all. So a UI keyed on `projects.status` will usually miss the rebuild entirely while a client
keyed on the 409 still sees it a minute later. The console reads the window off the polled document
rows instead.

</details>

## Security

[`SECURITY.md`](SECURITY.md) states what this system does and does not promise, scenario by
scenario with the control and the gap for each:

- **Prompt injection.** An uploaded document can make an NPC say anything. It cannot reach another
  tenant's lore, the credential vault, or a tool, because there are none. Retrieved lore is
  appended to the **system** message, so it speaks with the persona's own authority — there is no
  privilege boundary, and the threat model is tolerable only because documents are uploaded by the
  project's own owner.
- **The API key in the game route's URL path**, which lands in proxy and access logs. Documented as
  accepted for self-hosted use; re-examined for hosted. It is also the reason `SENTRY_DSN` cannot be
  switched on without a scrubber: an error tracker collects the full request URL by default, and a
  SaaS is not a log the operator controls. `core/scrubbing.py` replaces that one path segment,
  keeps the rest so the event stays findable, and redacts `X-API-Key`, `Authorization` and `Cookie`.
- **Abuse**, and which of the two knobs below bounds which half of it.

Multi-tenant isolation was audited live from two identities and is frozen as 20 cases in
`tests/test_tenant_isolation.py`, including the strong form of the vector probe: one tenant's
invented fact, queried through another tenant's project, must return *that tenant's own chunk*
rather than an empty list, which is what distinguishes a working filter from a broken index.

### Rate limits and quotas

**Both off by default**, so a fresh clone behaves like a local tool. Turn them on for any origin a
stranger can reach — until you do, a public deployment with an open `POST /v1/keys` and a
credential vault is an open proxy on your provider bill.

```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_COMPLETIONS_PER_MINUTE=30   # both completions shapes and POST /v1/chat
RATE_LIMIT_UPLOADS_PER_HOUR=60         # POST /v1/upload
RATE_LIMIT_DEFAULT_PER_MINUTE=120      # everything else, including POST /v1/keys

TOKEN_QUOTA_PER_MONTH=2000000          # 0 is unlimited
```

A refused request is a **429** with `Retry-After` in whole seconds. `/health` is never throttled:
the platform polls it forever, and throttling it would pull the instance out of the load balancer
under exactly the load the limiter exists to survive.

<details>
<summary><b>Three things to know before relying on either</b></summary>

- **Buckets are per process.** Everything stateful here already is — the object registry, the
  ingest queue, the session locks, the runtime cache — and making the limiter the one component
  that needs Redis would buy a shared store for the cheapest thing in the system. **With N replicas
  the effective limit is N × the number you configure.**
- **Identity is the API key's hash**, or the client host when there is no key. Not the resolved
  user: that costs a database round trip on every request, and verifying a JWT in middleware would
  add a JWKS fetch to the hot path. So a caller who mints ten keys gets ten buckets (bounded by
  `MAX_API_KEYS_PER_USER`, 25 live keys), and several console users behind one NAT share one. The
  second is the safe direction to be wrong: keying on an unverified token would let an attacker
  mint a fresh bucket per request.
- **The rate limit bounds frequency, not spend.** Thirty requests a minute with a 100k-token
  context on an expensive model is still a real bill. `TOKEN_QUOTA_PER_MONTH` is the other half: a
  rolling 30-day sum over `chat_messages.total_tokens`, checked **before** the provider is called,
  so the request that trips the quota is not the request that spends the money.

</details>

## Deployment

Two documents, for two different jobs. **[`DEPLOY.md`](DEPLOY.md) is the runbook for *this*
deployment** — hosts, environment, the three origin lists that must agree, backups, and what to
check first when chat stops working. **[`SELFHOST.md`](SELFHOST.md) is the guide for *yours*** —
which of the five choices to make, what running it actually costs, and the paragraph about `data/`
that decides whether your install can ever be reconfigured.

| Piece | Where |
| --- | --- |
| API | Render, region `singapore`, Docker |
| Console and site | Vercel |
| Postgres and auth | Neon, `ap-southeast-1` |
| Vectors | Qdrant Cloud, `eu-central-1` |

```bash
docker build -f deploy/Dockerfile -t sentient .
docker run -p 8000:8000 --env-file /tmp/env.unquoted -v sentient-data:/app/data sentient
```

Three things bite here and nowhere else.

**`docker --env-file` does not strip quotes** while `python-dotenv` does, so a `.env` line written
`DATABASE_URL="postgresql://…"` reaches the container with a literal `"` and asyncpg rejects the
DSN. Strip them first:
`sed -E 's/^([A-Za-z_][A-Za-z0-9_]*)="(.*)"$/\1=\2/' .env > /tmp/env.unquoted`.

**The image has no torch**, because it is built with `uv sync --no-default-groups`. Set
`EMBEDDING_PROVIDER` to a hosted provider; the local HuggingFace one has no model to run.

**`data/` must be a persistent volume.** It holds uploads, FAISS partitions and the SQLite
fallback, and uploads are an *input* to a reindex rather than a cache of one — `run_reindex_job`
re-reads every file from disk to rebuild. Without a volume, a restart leaves the rows and the
vectors alive while the files are gone, and a later rebuild is refused rather than silently
producing an empty index over a working one.

**`/health` is liveness and `/health/ready` is readiness**, and conflating them has already cost a
deployment. `/health` never touches the database, so it answers 200 while Postgres is unreachable;
a platform health check wired to it keeps a broken instance in rotation. Point the platform at
`/health/ready`, which runs a real query and reports queue depths alongside.

## Development

```bash
uv run python -m pytest tests/ -v                     # 518 tests
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src/sentient/core src/sentient/adapters   # strict on the Protocol seams
uv run lint-imports                                   # the layer contract
```

CI runs all five on every push and pull request. Add dependencies with `uv add`; never hand-edit
`uv.lock`.

The console has its own four, run from `apps/console` and wired into their own workflow:

```bash
npm run lint            # the layer contract and the fetch-seam ban
npm run test            # vitest
npm run build           # vite build, THEN tsc --noEmit -- routeTree.gen.ts is generated
npx prettier --check .
```

Tests never touch the network. Qdrant runs at `location=":memory:"`, embeddings are faked, and
provider clients are patched — which means anything that only breaks against a real service breaks
in production first, and is why every external dependency has a recorded manual verification behind
it.

## Roadmap

Nothing that blocks use is outstanding. What remains is operability and launch:

- **Observability.** Optional Sentry for exceptions and Langfuse for per-turn traces. Neither
  exists yet, so today a production exception reaches nobody and no one can say where a slow turn's
  seconds went.
- **Recovery drills.** Backups are configured and the procedures are written down; neither the
  rollback nor the restore has actually been executed once.
- **Launch documentation.** A Mantella setup guide for modders, a self-host guide with honest
  running costs, and a support path.
- **`PgVectorBackend`.** One store instead of two retires the cross-region hop, the disk question,
  the restore-consistency problem and the memory cost in a single change, and the Protocol seam it
  plugs into already exists.
- **A retrieval eval set**, because there is currently no way to tell whether a configuration
  change made grounding better or worse.

## License

**MIT.** See [LICENSE](LICENSE). Use it, fork it, host it, sell something built on it.

The dependency tree is checked against that intent rather than assumed to match it: the S4 audit
found `pymupdf` was AGPL-3.0 and a *direct* dependency, which would have imposed a source-offer
obligation on anyone hosting a modified copy. It was replaced with `pypdfium2` (BSD/Apache) on
2026-08-27, and `uv run --with pip-licenses pip-licenses` now reports no AGPL anywhere. Both models
in the default path clear commercial use too, verified against their cards:
`BAAI/bge-base-en-v1.5` is MIT and `Qdrant/bm25` is Apache-2.0.

## Using the hosted deployment

The instance at `sentient-console.vercel.app` is free, best-effort and run by one person.
[TERMS.md](TERMS.md) says what that does and does not promise; [PRIVACY.md](PRIVACY.md) says what
is stored, and the two things worth knowing before you sign up are that **it keeps your full
conversation transcripts** — including ones held in-game, where no console is open — and that your
provider API keys are stored encrypted under a server-side key.

## Support

Report anything at <https://github.com/prabhjot0109/sentient/issues>. There are three templates and
the first one — *My NPC won't talk* — asks for the five things that would otherwise cost a second
round trip: the origin, whether you self-host, the provider, whether the project was rebuilding, and
Mantella's last log lines.

**Check what you paste.** Your `sk-sent-` key is inside the base URL and the base URL is in the
logs. If one is exposed, revoke it in the console; revocation takes effect immediately.

For a security vulnerability, open a private advisory instead — [SECURITY.md](SECURITY.md). The
operator's side of a report is the triage table in [DEPLOY.md](DEPLOY.md#triage-someone-has-reported-a-problem).
