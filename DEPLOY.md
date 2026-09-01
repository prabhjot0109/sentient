# Deploying Sentient

The runbook for putting Sentient on a real origin and keeping it there. It assumes you have
already read `README.md`; this file only covers what is different about running the service for
other people.

`docs/` is untracked, so anything a future operator needs lives here rather than in a plan file.

---

## What runs where

| Piece | Host | Live at |
| --- | --- | --- |
| `sentient-api` | Render, region `singapore`, Docker from `deploy/Dockerfile` | `sentient-api-54r2.onrender.com` |
| `sentient-console` | Vercel, root directory `apps/console` | `sentient-console.vercel.app` |
| `sentient` (landing) | Vercel, root directory `apps/landing` | `sentient-npc.vercel.app` |
| Postgres + Auth | Neon, `ap-southeast-1`, branch `production` | endpoint `ep-muddy-rice` |
| Vectors | Qdrant Cloud, `eu-central-1` | collection `sentient_lore_prod` |

The API is a stateful single-process container; the two frontends are static Vite builds with
nothing to run. Neon is the authoritative store — users, keys, projects, documents, threads, every
message. Qdrant holds derived data with a rebuild path, which is why it is the one allowed to sit
in another region.

**The console origin appears in three separate places and they must agree**: Render's
`CORS_ALLOW_ORIGINS`, Neon Auth's trusted-domain list, and landing's `VITE_CONSOLE_URL`. Renaming a
Vercel project or adding a custom domain means updating all three, and each failure looks
different. Both of the console's Vercel domains are currently trusted, so an alias change does not
break sign-in on its own.

`render.yaml` and the two `vercel.json` files are the committed form of all of this. A redeploy
from nothing is those three files plus the secrets.

### Why the regions are what they are

Render's `region` is **immutable** after the service is created, and so is a Neon project's. They
are the two decisions here you cannot walk back, so they were made deliberately.

Neon is in Singapore, which is also where the operator is, so `sentient-api` goes to Singapore
too. Every Postgres round trip then costs about 2 ms instead of about 160 ms, and a turn makes
several of them before the first token.

The Qdrant free tier does not offer an Asian region, so the cluster is in Frankfurt and the
retrieval leg pays that ~160 ms hop. That is the one deliberate inefficiency in the topology, and
it is the right one to accept: against a 1–3 s generation it is roughly a 10% slowdown, and
**vectors are derived data.** Moving them later is a reindex from the console. Moving Postgres
would be a migration of the only store that holds anything unrecoverable, and it would put the
database 140 ms from every user in Asia to save a hop that is going away anyway.

The hop goes away for good when vectors move into Neon itself with `pgvector`. That is a new
`VectorBackend` implementation, not a config change, and it is the intended destination.

---

## Where uploaded files live

**Read this paragraph before deploying. It is the one that will otherwise bite you.**

`services/ingestion.py::run_reindex_job` rebuilds a project by re-reading every uploaded file
from `DATA_DIR`. That makes `data/` an **input** to a rebuild, not a cache of one. The rows in
Postgres and the vectors in Qdrant both survive a restart. The uploaded files do not, because the
Render free plan has no persistent disk.

So after any restart, a project's chat keeps working — the vectors are still in Qdrant — but its
source files are gone. Changing the embedding model in project settings queues a reindex, and
that reindex has nothing to read.

As of `903e8a9` the job **refuses before purging anything**: the surviving vectors stay, the
affected document rows go to `failed`, and the project stays at `reindexing_required` until the
user re-uploads and reindexes. Before that fix the same path destroyed a working index and left
the project answering 409 for good, with its rows frozen on a status nothing clears.

Two ways to remove the limitation entirely, in increasing order of effort:

1. **Take a paid instance and mount a disk at `/app/data`.** Files persist; a disk pins the
   service to one instance and disables zero-downtime deploys, both of which are already true
   here.
2. **Move uploads to object storage**, or store them in Postgres alongside the rows that
   reference them. This is the one that also removes the disk from the backup story.

---

## What the free plan costs you

| | Consequence |
| --- | --- |
| Spins down after ~15 minutes idle | The next request pays a cold start. **Measured 2026-09-01 against the live service after an overnight idle: 6 seconds** to a 200 from `/health/ready`. That is a pause before the first NPC line, not a timeout, and it is a direct result of dropping torch — the same boot cost 20 s of import alone beforehand. |
| No persistent disk | See above. |
| 512 MB RAM | The app imports at ~147 MB after `40c1106` made torch optional; it was 305 MB before, which did not leave room for ingestion. Do not put `sentence-transformers` back into the default dependencies. |
| No custom domains | You are on `*.onrender.com`, and that hostname is what goes in `CORS_ALLOW_ORIGINS` and Neon Auth's trusted-domain list. Both change when you move to a domain. |

---

## Deploying, in order

### 1. Promote Neon to `production`

Neon Auth is **branch-scoped**. Each branch has its own auth environment, its own JWKS host, and
its own users — accounts created against `dev-console` do not exist on `production`.

```bash
neon branches list
neon connection-string production --pooled     # DATABASE_URL
neon neon-auth env production                  # JWKS URL, issuer, base URL
```

Migrations in `migrations/` are applied by `PostgresStateStore` the first time it opens a pool,
so the first connect from the deployed service is a migration event. Watch the logs for it and
confirm the tables exist afterwards.

Google sign-in needs its own OAuth client on this branch. Neon's shared app is explicitly
dev-only — its consent screen carries Neon's branding:

```bash
neon neon-auth oauth-provider add --provider-id google --branch production \
  --oauth-client-id <id> --oauth-client-secret <secret>
```

### 2. Create `sentient-api` on Render

Point Render at this repo and let it read `render.yaml`. Then set every variable marked
`sync: false` in the dashboard.

Before trusting the platform's build log, build it yourself — the Dockerfile copies `src/` before
`uv sync` because the project is an installed package, and getting that wrong fails in a way
Render's log makes hard to read:

```bash
docker build -f deploy/Dockerfile -t sentient:probe .
docker run --rm -p 8000:8000 --env-file .env sentient:probe
curl -s http://127.0.0.1:8000/health/ready | jq .
```

**`docker --env-file` does not strip quotes, and `python-dotenv` does.** If a value in `.env` is
written `DATABASE_URL="postgresql://…"`, the container receives a string that begins with a literal
`"` and asyncpg rejects it with `invalid DSN: scheme is expected to be either "postgresql" or
"postgres", got ''`. It works in development and fails only in the container, because the image
never loads `.env` at all — nothing is there to strip the quotes. Strip them for a local run:

```bash
sed -E 's/^([A-Za-z_][A-Za-z0-9_]*)="(.*)"$/\1=\2/' .env > /tmp/env.unquoted
docker run --rm -p 8000:8000 --env-file /tmp/env.unquoted sentient:probe
```

This does not affect Render, which sets variables individually with no quoting.

**Measured from this image on 2026-09-01**, against the real Neon branch and the real Qdrant
cluster:

| | |
| --- | --- |
| Image size | 220 MB |
| Idle resident memory | **199 MB** of the 512 MB budget |
| Warmup | 4.2 s to "startup complete" |
| `torch` / `transformers` / `sentence_transformers` | not installed |
| `tesseract` | 5.5.0 |
| `/health/ready` | 200, `{"ready": true, "checks": {"state_store": "ok", …}}` |
| Docker `HEALTHCHECK` | reports `healthy` |

The memory figure is the one that matters. It leaves roughly 310 MB of headroom for ingestion,
which rasterises PDF pages at 200 DPI. Before torch was made optional the same container idled
near 460 MB and had essentially none.

One thing the first boot does that the logs make obvious: FastEmbed **downloads its sparse BM25
model** ("Fetching 18 files"). On a free instance that spins down, this is a network fetch on
every cold start, and it is part of why the first request after idle is slow.

Then confirm the config the process actually resolved, from inside the container rather than from
the dashboard. Hosts and booleans only, never a secret's value:

```bash
python -c "
import sentient.api.app
from sentient.core.config import load_rag_settings
s = load_rag_settings()
for f in ('llm_provider','llm_model','embedding_provider','embedding_model','vector_backend','qdrant_collection'):
    print(f'{f:22} {getattr(s, f)}')
print('database host        ', (s.database_url or '').split('@')[-1].split('/')[0])
print('jwks host            ', (s.neon_auth_jwks_url or '').split('/')[2] if s.neon_auth_jwks_url else None)
print('auth enabled         ', bool(s.neon_auth_jwks_url))
print('vault configured     ', bool(s.sentient_secret_key))
print('rate limiting        ', s.rate_limit_enabled)
"
```

`import sentient.api.app` first, or the probe reports the fallback provider while the server runs
on something else. This exact mistake produced a false positive on an earlier verification run.

### 3. Deploy the two frontends to Vercel

Two projects from the same repo, root directories `apps/console` and `apps/landing`. Each has a
`vercel.json` that sets the SPA rewrite; without it, TanStack Router's client-side routes 404 on
a page reload, because Vercel would look for a file that does not exist. Rewrites are evaluated
after the filesystem check, so the catch-all does not shadow `/assets/*`.

Console build variables:

- `VITE_API_BASE_URL` — the Render origin, `https://…onrender.com`, no trailing slash.
- `VITE_NEON_AUTH_URL` — the **`production`** branch's auth base URL.

Landing build variable:

- `VITE_CONSOLE_URL` — the console's Vercel origin plus `/auth/sign-up`.

**These are Vite variables, so they are baked into the bundle at build time, not read at
runtime.** Nothing re-reads them when the page loads. Setting one after a deploy changes nothing
until the project is redeployed, and a build that ran before the variable existed produces a
console that quietly points at `http://127.0.0.1:8000` — the fallback in `lib/api/client.ts` — and
fails every request from a hosted origin with no message naming the cause.

So set both variables **before** the first deploy, and redeploy after changing either. They carry
no secrets: a public SPA cannot hold one, which is also why Google sign-in has no variable here at
all and is configured per branch on Neon's side.

The projects are `sentient-console` (root `apps/console`) and `sentient` (root `apps/landing`).
The landing project is deliberately the bare name, because it owns the apex domain a visitor
types; the console is a subdomain of the same idea and says so in its name.

### 4. Make the three origin lists agree

This is where deployments fail, and it fails in three different places with three different
symptoms — two of which look identical from the browser.

```bash
# 1. The backend's CORS allow-list. api/app.py permits any localhost/127.0.0.1
#    port by regex, which covers development and nothing deployed.
CORS_ALLOW_ORIGINS=https://<console-origin>

# 2. Neon Auth's trusted domains. The list is EMPTY; local development works only
#    because allow-localhost is true.
neon neon-auth domain add https://<console-origin> --branch production
```

3. The console's `VITE_NEON_AUTH_URL` must name the same branch as the backend's
   `NEON_AUTH_JWKS_URL`.

Verify the preflight from the real origin:

```bash
curl -s -i -X OPTIONS "https://<api-origin>/v1/projects" \
  -H "Origin: https://<console-origin>" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization" | head -20
```

Expect 200 or 204, `access-control-allow-origin` echoing the console origin, and
`access-control-allow-headers` including **`authorization`**. That last one is the one that
matters: an allow-list without it passes the preflight and then fails every real request.

### 5. Smoke it from outside

```bash
curl -s https://<api-origin>/health | jq .
curl -s https://<api-origin>/health/ready | jq .
curl -s -o /dev/null -w '%{http_code}\n' https://<api-origin>/v1/projects    # 401, auth is on
```

Then the whole walk through the browser: sign up, create a project, upload lore, mint a key, and
hold a conversation over `/v1/<key>/<project_id>/chat/completions`. Anything that needs
`127.0.0.1` to work is a finding — that rule is a Windows loopback cost and does not apply
between two deployed hosts.

---

## Two things the first real deploy taught, both worth keeping

**A healthy service can be completely unreachable, and the dashboard will say it is live.**
Measured 2026-08-31. The container started, uvicorn logged `Uvicorn running on
http://0.0.0.0:8000`, `/health/ready` answered 200 to Render's checker every five seconds, the
deploy was marked live — and every public request returned 404 with the header
`x-render-routing: no-server`.

The cause is three lines apart in the build log:

```
INFO:  127.0.0.1:55954 - "HEAD / HTTP/1.1" 404 Not Found
==>   No open ports detected, continuing to scan...
==>   Your service is live 🎉
```

Render's port scanner probes `HEAD /` and reads a 404 as "nothing serving on this port", so the
port never enters the routing table. **Liveness and routing are decided separately**, which is why
the health check passing tells you nothing about whether traffic arrives. Fixed by the `/` route in
`routers/health.py`, registered for GET **and** HEAD — FastAPI does not derive HEAD from GET, and a
`@router.get("/")` answers `HEAD /` with 405, which the scanner treats no better than the 404.

If a Render service ever looks healthy and serves nothing, check that header first. `no-server`
means the routing table, not the app.

**Check which Neon branch the service actually reached, by looking at the schema.**
`PostgresStateStore._ensure_schema` applies every file in `migrations/` on its first successful
pool creation, with no error handling. So the tables are a fingerprint: if a branch is missing
`chat_messages`, `provider_credentials`, `chat_threads.prefix_hash` or `documents.size_bytes`, then
nothing that runs this code has ever connected to it — whatever `DATABASE_URL` you believe is set.

That is how a branch mismatch was caught here: the service was healthy and answering, `production`
had six tables and no `chat_messages`, and therefore the running service was on `dev-console`.
Pasting the DSN out of `.env` is the easy way to do this, because `.env` holds the development
branch.

```sql
select table_name from information_schema.tables where table_schema='public' order by table_name;
```

Eight tables means every migration ran. Six means the branch is stale and something else is
serving your traffic.

## Health checks: two routes, two questions

`/health` is **liveness**. "This process is running." It reads the archive and the settings and
never touches the database, so it answers 200 during a database outage. That is correct for
liveness and wrong for anything else.

`/health/ready` is **readiness**. "This instance can serve a request." It runs a real query
against the state store and answers 503 with the failing check named. Render's health check
points here, and it must stay pointed here — wired to `/health`, a broken instance stays in
rotation serving 500s.

It also reports `ingest_queue_depth` and `reindex_queue_depth`. Those are **reported, not
asserted on**: a deep queue means busy, not unhealthy, and failing readiness on it would pull the
instance out exactly when it has the most work in flight.

The probe queries `list_projects` against the **nil UUID**, and the well-formedness is not
cosmetic. `projects.user_id` is a `uuid` column on Postgres and asyncpg refuses to *bind* a
non-uuid string to one, raising `DataError` before the query is sent. A readable sentinel like
`"__readiness_probe__"` passes the whole test suite, which runs on SQLite, and then answers 503
against a completely healthy Neon. That happened here on 2026-09-01 and was only caught by running
the image against the real branch.

The fix belongs in the probe and **not** in an `_is_uuid` guard on `list_projects`, which would
return an empty list without opening a connection — readiness would report `ok` while the database
was unreachable, which is the exact defect the route exists to remove.

---

## When chat stops working, check these three first

1. **`/health/ready`.** A 503 names the failing subsystem, and it is almost always the database.
   A 200 here means the problem is downstream of the platform.
2. **The provider.** A dead or unfunded provider key is the single most common cause. Every
   credential in `.env` has been found dead at once before. The console surfaces the provider's
   own message; a 402 or 401 from Groq or Google says so in words.
3. **The origin lists.** If it is only broken in the browser and `curl` is fine, it is CORS or
   Neon Auth's trusted domains, not the backend. A blocked preflight shows up in the browser
   console as a network failure with no status code at all, which is why the rate limiter is
   added *inside* CORS in `api/app.py::configure_middleware` — otherwise a 429 would arrive
   looking like an outage.

`.env` is read at import, so a live process never sees a new key. Restart after changing one.

---

## Rolling back

Render keeps previous deploys and can roll back to one from the dashboard. **Do this once
deliberately before you need it**, with a deliberately broken revision, and write the measured
time here:

- Time to detect: _____
- Time to roll back and confirm service: _____

A rollback path you have not executed is a belief, not a plan.

---

## What happens if the service restarts mid-ingest

`IngestQueue` and `defer` are in-process and not crash-durable, so a restart during an ingest
loses the job. Startup reconciliation fails orphaned `processing` rows, so the document lands as
`failed` rather than spinning forever, and the user's recovery is to upload it again.

That is a deliberate stopping point rather than an oversight. Durable background work means a
shared broker, which is the same prerequisite as running more than one instance, and the exposure
window here is a single ingest measured in seconds to minutes. What matters is that the failure
is **visible and recoverable by the user**, and it is.

Note the gap this does *not* cover: reconciliation fails `processing` rows only. A crash during a
**reindex** leaves rows at `reindexing`, which nothing clears.

---

## Backups

| Store | Mechanism | Notes |
| --- | --- | --- |
| Neon | Point-in-time restore | A restore creates a **branch**, so recovery is fast but the connection string changes. Check the retention window on the plan you are actually on. |
| Qdrant | Per-collection snapshots, on demand | A snapshot stored on the same cluster is not a backup of that cluster. |
| `data/` | None on the free plan | It has no disk. See "Where uploaded files live". |

Postgres and Qdrant are separate systems with separate clocks, so they cannot be restored to a
consistent moment. A restore can leave document rows referencing vectors that no longer exist, or
vectors with no row. Both are recoverable by reindexing, which is another reason vectors are the
half worth treating as derived.

**Do the restore drill once, on a branch, never against production**, and record how long each
step took.
