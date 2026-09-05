# Self-hosting Sentient

[DEPLOY.md](DEPLOY.md) is the runbook for *the* deployment — Render, this Neon project, this Qdrant
cluster. This is the guide for **yours**, where the interesting part is the choices you get to make
and which one of them actually matters.

MIT licensed. Host it, modify it, charge for it.

---

## The choices, decided for you

| | Default | Take the other one when |
| --- | --- | --- |
| Vector store | **FAISS**, on local disk | You have no persistent disk, or more than one tenant. Then Qdrant. |
| Relational store | **SQLite**, at `data/state.db` | More than one user, or no persistent disk. Then Postgres via `DATABASE_URL`. |
| Auth | **Off** — one user, `default` | Anyone but you can reach the origin. Then Neon Auth. |
| Embeddings | Whichever provider key you set | You want no API bill and have the RAM. Then `EMBEDDING_PROVIDER=huggingface`, and see the torch note below. |
| Rate limits and quota | **Off** | The origin is reachable from the internet. Always, then. |

**A single-player Skyrim setup needs none of this.** `uv sync`, one provider key,
`uv run uvicorn sentient.api.app:app`, and the defaults are correct: FAISS on disk, SQLite beside
it, no auth because there is one of you. Everything below is for putting it somewhere other people
can reach.

---

## The paragraph that decides whether your install works

**`data/` is an INPUT to a rebuild, not a cache of one.**

`services/ingestion.py::run_reindex_job` rebuilds a project by re-reading every uploaded file from
`DATA_DIR`. So when you change a project's embedding model — which is the whole point of having the
setting — the job needs those original files.

On a host with no persistent volume the rows in your database and the vectors in your vector store
both survive a restart. **The uploaded files do not.** The project keeps answering fine, because the
vectors are still there, right up until someone changes a retrieval setting. Then the rebuild has
nothing to read.

Since `903e8a9` the job **refuses before purging anything**: the surviving vectors stay, the
affected document rows go to `failed`, and the project sits at `reindexing_required` with a reason
attached explaining exactly this. Before that fix it destroyed a working index first and discovered
the problem afterwards.

**Mount a volume at `/app/data`.** If your platform's free tier has no disk, know that you have
bought a deployment whose projects cannot be reconfigured, and that this is the reason.

---

## Docker

```bash
docker build -f deploy/Dockerfile -t sentient .
docker run -p 8000:8000 -v sentient-data:/app/data --env-file .env sentient
```

### Two traps that bite here and nowhere else

**`docker --env-file` does not strip quotes; `python-dotenv` does.** A `.env` line written
`DATABASE_URL="postgresql://…"` works perfectly in development and fails only inside the container,
where asyncpg receives a string beginning with a literal `"` and answers
`invalid DSN: scheme is expected to be either "postgresql" or "postgres", got ''`. The image never
loads `.env` at all, so nothing is there to strip them. For a local run:

```bash
sed -E 's/^([A-Za-z_][A-Za-z0-9_]*)="(.*)"$/\1=\2/' .env > /tmp/env.unquoted
docker run --env-file /tmp/env.unquoted …
```

Platforms that set variables individually (Render, Fly, Railway) are unaffected.

**The image has no torch, deliberately.** It is built with `uv sync --no-default-groups`, which
drops the `local-embeddings` group and with it `sentence-transformers` — the only package in the
tree that requires torch. Measured 2026-08-31: importing the app costs **305 MB and 20.0 s** with
torch present and **147 MB and 3.3 s** without, against a 512 MB budget.

So `EMBEDDING_PROVIDER=huggingface` **does not work on the default image**. It fails with an error
naming the group rather than silently, but it fails. If you want local embeddings and no API bill,
build your own image with the group in:

```dockerfile
RUN uv sync --frozen --no-default-groups --group local-embeddings --group observability
```

and size the host for it: 512 MB is not enough once ingestion also has to rasterise PDF pages.

**One worker, and this is not tunable yet.** Every stateful component in the process is per-process:
`ObjectRegistry`, `IngestQueue`, `SessionLocks`, `RuntimeCache`, and the rate-limit buckets. Two
workers means two of each — a job enqueued on worker A is invisible to worker B, and your effective
rate limit doubles. Scale up before you scale out.

**`tesseract-ocr` is the binary, not the Python package.** The Dockerfile installs it. Without it,
`pytesseract` imports fine, every scanned PDF ingests as **zero text**, and the upload reports
success. If you build your own image, keep that line.

---

## Postgres, Qdrant, or Pgvector

Set `DATABASE_URL` and the store switches; `migrations/*.sql` are applied on the first connect, so
the first request after a deploy is a migration event. Watch for it in the logs.

Set `VECTOR_BACKEND=qdrant` plus `QDRANT_URL` and `QDRANT_API_KEY`, and prefer gRPC
(`QDRANT_PREFER_GRPC=true`) against Cloud.

### Pgvector: one database, one region, one recovery clock

Set `VECTOR_BACKEND=pgvector` and run `uv sync --group pgvector`. It uses the same
`DATABASE_URL` (or `SUPABASE_DB_URL`) as `PostgresStateStore`; migration `0007_pgvector.sql`
creates the `vector` extension and the table on the first connection. That removes the Singapore →
Frankfurt retrieval hop, the separate Qdrant account, and the Postgres/Qdrant restore inconsistency
window in one change.

The table uses pgvector's variable-dimension `vector` type, so projects may use different embedding
models or MRL dimensions. It deliberately starts with a normal SQL scope index and cosine ranking,
not a guessed HNSW index: pgvector requires an expression/partial HNSW index for each dimension, so
add one only after real traffic tells you which model/dimension dominates. Tenant, project and
embedding-signature filters are in every query before ranking.

### Two Qdrant limits that only appear at scale, and both surprise people

**Every tenant on a Qdrant deployment shares one embedding dimension.** The collection is created
once, at whatever dense dimension writes to it first, and `_ensure_collection_sync` never revisits
that. A second project on a differently sized model gets
`Existing Qdrant collection is configured for dense vectors with 3072 dimensions. Selected
embeddings are 768-dimensional.` FAISS has no such limit — each partition is its own index. Choose
the embedding model before the first upload, or plan on a new collection.

**`RAG_SCORE_THRESHOLD` means something different on each backend.** On FAISS it is a cosine floor
and it filters. On Qdrant, hybrid scores are **rank-fusion artefacts**, not similarity: measured on a
project whose only chunk was one invented fact, the matching query scored **1.0** and the nonsense
string `zzqqx wubblefarn grimplenock` scored **0.5** — clearing a configured floor of 0.2. The knob
is inert below 0.5 there. Never tune it against one backend and deploy the other.

`/health`'s `index_metadata` also has a different shape per backend: FAISS returns
`sources` / `source_count` / `persona` / `updated_at`, Qdrant returns `backend` / `collection`.

---

## Before anyone else can reach it

- **`RATE_LIMIT_ENABLED=true` and `TOKEN_QUOTA_PER_MONTH`.** They are not substitutes: the limiter
  bounds *frequency*, the quota bounds *spend*. Thirty requests a minute against a 100k-token
  context on an expensive model is a real bill. Two documented gaps: buckets are per **process**, so
  N replicas means N× the number, and identity is the API key's **hash**, so a user's ten keys buy
  ten buckets — capped at 25 live keys by `MAX_API_KEYS_PER_USER`.
- **`SENTIENT_SECRET_KEY`.** Without it the credential vault answers 503 and every user runs on
  *your* provider key. Rotating it needs `SENTIENT_SECRET_KEY_OLD` present for one deploy; without
  that, rotation **does not error** — it silently sends every user to the env key, and the first
  symptom is a bill.
- **`NEON_AUTH_JWKS_URL` and `NEON_AUTH_BASE_URL`.** Both. The issuer is derived from the second,
  and with neither set PyJWT's issuer check returns early on `None` — verification is silently off
  while authentication stays on.
- **`CORS_ALLOW_ORIGINS`** must name your console's origin, and if you use Neon Auth its
  trusted-domain list must too. They fail differently: a blocked preflight is a network error with
  no status, and an untrusted domain is `invalid domain` in a response body.
- **`SENTRY_DSN`**, optionally. It needs `--group observability` in the image; the blueprint gate
  in this repo checks that pairing because a DSN with no SDK boots, serves, and reports nothing.

---

## What it costs to run

Honest, and separated into the two halves people conflate.

### Infrastructure

| Piece | Free tier | What it costs you | First paid step |
| --- | --- | --- | --- |
| API host (Render free) | 0.15 CPU, 512 MB, no disk, sleeps after ~15 min | **This is the constraint behind every slow number in this repository.** OCR at ~60 s/page against ~8 s on a laptop; a 6-page scan at 15m51s; a ~6 s cold start | ~$7/mo for a dedicated instance and a mountable disk |
| Postgres (Neon free) | Enough for a personal deployment | Compute suspends when idle, so the first query after a pause is slow | ~$19/mo |
| Vectors (Qdrant Cloud free) | 1 GB, one region | No Asian region on free, hence a ~160 ms hop for this deployment | ~$25/mo |
| Frontends (Vercel free) | Static builds | Nothing | — |

**Buying the API instance is the single highest-value spend**, and it is not close. 0.15 CPU is a
roughly 7× penalty on the one operation users actually wait for.

### Model spend

**Bring your own key is the intended answer**, and the credential vault exists for it: with a user's
key stored, their traffic runs under their own agreement with the provider and you resell nothing.
That also decides what `TOKEN_QUOTA_PER_MONTH` is *for* — a fairness control rather than a cost
control, and those want different numbers.

The exposure is the fallback: with no stored credential, resolution falls through to the
deployment's own key. On a public origin that is your key serving strangers. **The clean answer for
a hosted deployment is to refuse to serve a user who has stored no credential**, which removes the
question entirely.

To price your own traffic, do not estimate what you can query — `chat_messages.total_tokens` is
already recorded per turn:

```sql
select date_trunc('day', created_at) as day,
       model,
       count(*)          as turns,
       sum(total_tokens) as tokens
from chat_messages
where total_tokens is not null
group by 1, 2
order by 1 desc;
```

Multiply by your provider's published rate. `total_tokens` is nullable on purpose — a user message
has none, and some providers report none — so a `sum` over it is a floor, not a total.

---

## Verifying you got it right

```bash
curl -s https://your-origin/health/ready | jq .
```

`/health` and `/health/ready` answer different questions and conflating them has already cost one
deployment. `/health` reads the archive and the settings and **never touches the database**, so it
answers 200 while Postgres is unreachable — a platform health check wired to it keeps a broken
instance in rotation. Point the platform at `/health/ready`, which runs a real query and reports
queue depths.

Then walk the real path once: sign up, create a project, upload a small text file, wait for `ready`,
mint a key, and ask an NPC something only that file knows. Anything the test suite does not do is
untested, and the quickstart is full of things it does not do.
