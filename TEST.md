# Manual test plan

What a person has to check by hand, because no gate can. Everything else is already
automated — **do not re-test the automated list by hand**, it is a waste of an hour.

Counts here were regenerated on 2026-08-28, not copied. Regenerate them rather than
trusting them:

```bash
uv run python -m pytest tests/ --collect-only -q | tail -1   # 434
cd apps/console && npm test                                  # 82
curl -s http://127.0.0.1:8000/openapi.json | python -c "import json,sys;print(len(json.load(sys.stdin)['paths']))"   # 25
```

---

## 0. What the gates already cover

| Gate                                                  | Covers                                                                                              |
| ----------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `uv run python -m pytest tests/`                      | 434 backend tests, incl. 20 tenant-isolation cases                                                  |
| `uv run ruff check` / `ruff format --check`           | lint + format                                                                                       |
| `uv run mypy src/sentient/core src/sentient/adapters` | typing on the Protocol seams                                                                        |
| `uv run lint-imports`                                 | the `api → services → adapters → core` layer contract                                               |
| `cd apps/console && npm test`                         | 82 cases: the fetch seam's 401-retry, the SSE parser, transcript settling, error copy, poll backoff |
| `npm run lint` (console)                              | the `routes → features → lib → types` layer contract + the `fetch` ban                              |
| `npm run build` (console)                             | `tsc --noEmit`                                                                                      |

All five backend gates and all four console gates run in CI on every push
(`.github/workflows/ci.yml`, `console.yml`, `landing.yml`).

**So the manual passes below are only for what a test suite structurally cannot assert:**
rendering, the browser's own behaviour, the real Neon Auth flow, and the actual game.

---

## 1. Setup — once

```bash
# Backend env. Ask for a real provider key; every check in pass G needs one.
cp .env.example .env          # then fill DATABASE_URL, NEON_AUTH_*, a provider key

# Console env. The auth URL is PER BRANCH and rots — pull it, never paste a literal.
neon env pull                 # writes NEON_AUTH_BASE_URL at the repo root
cp apps/console/.env.example apps/console/.env.local
#   VITE_NEON_AUTH_URL  = that NEON_AUTH_BASE_URL
#   VITE_API_BASE_URL   = http://127.0.0.1:8000
```

**The two host rules are opposites and both are real. Getting either wrong wastes an hour.**

| Hop                                          | Use             | Why                                                                                                                                        |
| -------------------------------------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| browser → backend, Mantella → backend        | `127.0.0.1`     | uvicorn binds IPv4 only; Windows tries `::1` first — 208 ms wasted per request                                                             |
| **the console's own address in the browser** | **`localhost`** | Neon Auth rejects `http://127.0.0.1:<port>` with `INVALID_ORIGIN`. **Every sign-up fails**, and the form only says the sign-up was invalid |

Confirm Google is enabled on your branch before pass A5:

```bash
neon neon-auth oauth-provider list --branch <branch>    # expect: google  shared
```

## 2. Start the stack

```bash
uv run uvicorn sentient.api.app:app --host 127.0.0.1 --port 8000   # terminal 1
cd apps/console && npm run dev                                     # terminal 2 → :5175
cd apps/landing && npm run dev                                     # terminal 3 → :8080 (only for pass A1)
```

Health check before you start clicking — if this is not 200, nothing below is meaningful:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/health
```

---

## Pass A — the front door

| #      | Step                                       | Pass criteria                                                                              |
| ------ | ------------------------------------------ | ------------------------------------------------------------------------------------------ |
| **A1** | On `localhost:8080`, click **Get Started** | Lands on `localhost:5175/auth/sign-up`, showing **Sign Up** (not Sign In)                  |
| **A2** | Sign up with a throwaway email + password  | Lands on `/app`. No `INVALID_ORIGIN`                                                       |
| **A3** | Open devtools → Network, reload            | Requests to `127.0.0.1:8000` carry `Authorization: Bearer eyJ…`; `GET /v1/projects` is 200 |
| **A4** | Reload the page                            | You stay signed in. **Does not bounce to sign-in** — the three-state guard                 |
| **A5** | Sign out, then **Sign in with Google**     | Google consent (shows Neon branding — expected on the shared app), returns to `/app`       |
| **A6** | Sign out                                   | Full reload to `/auth/sign-in`; Back does not restore the signed-in shell                  |

> A5 is the one thing that cannot be checked without a browser and cannot be checked
> without a Google account. If it fails with a redirect-URI error, the branch's OAuth
> provider is missing — see §1.

## Pass B — themes, responsive, keyboard

**Never executed on this project.** F11 and the 2026-08-28 round both left it to the
operator. It is the highest-value pass here for that reason.

| #      | Step                                                                                             | Pass criteria                                                                              |
| ------ | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| **B1** | Click the sun/moon in the sidebar footer                                                         | Whole app repaints. **No white flash, no half-themed panel**                               |
| **B2** | Reload after switching                                                                           | The choice sticks; no flash of the other theme on load                                     |
| **B3** | In light mode, visit every screen: home, a conversation, Lore, Settings, API keys, Provider keys | No grey-on-grey text anywhere. Every label readable                                        |
| **B4** | In light mode, sign out and look at the sign-in card                                             | Neon's **prebuilt** AuthView is light too, including the Google button                     |
| **B5** | Resize to 375 / 768 / 1440                                                                       | No horizontal scrollbar. Below 768 the rail is a drawer behind the ☰                      |
| **B6** | At 375, open the drawer and pick a conversation                                                  | Drawer closes on navigation. Rename/Delete on a conversation are **visible without hover** |
| **B7** | From the address bar, press Tab repeatedly through a whole screen                                | Every focused control has a **visible ring**. Focus never lands on something invisible     |
| **B8** | Open any dialog (Rename, Delete), press `Escape`                                                 | Closes, and focus returns to the control that opened it                                    |

## Pass C — projects and the rail

| #      | Step                                 | Pass criteria                                                                          |
| ------ | ------------------------------------ | -------------------------------------------------------------------------------------- |
| **C1** | Fresh account, `/app`                | First-run empty state, not a blank page                                                |
| **C2** | Create a project                     | Appears in the rail; you land on its home                                              |
| **C3** | Create a second, switch between them | The **open** project is visibly highlighted (this was invisible before 2026-08-28)     |
| **C4** | Rename, then delete a project        | Rail updates. Deleting the open one navigates away; deleting a background one does not |
| **C5** | With projects, go to `/app` directly | Redirects into a project — never "Pick a project from the sidebar"                     |

## Pass D — lore

| #      | Step                                           | Pass criteria                                                                            |
| ------ | ---------------------------------------------- | ---------------------------------------------------------------------------------------- |
| **D1** | **Lore** tab → upload a PDF and a .txt         | Rows appear as `processing`, then reach `ready` **without a manual reload**              |
| **D2** | Watch a large file                             | Polling backs off, never stops. Status still updates after a minute                      |
| **D3** | Upload something invalid (a .zip renamed .pdf) | A readable failure naming the file — not "Unprocessable Content"                         |
| **D4** | Delete a document                              | Typed-name confirmation required; row disappears                                         |
| **D5** | Change the embedding model in **Settings**     | Warns about the reindex **before** saving, then the rail shows "re-embedding your lore…" |

## Pass E — the conversation

| #      | Step                                           | Pass criteria                                                         |
| ------ | ---------------------------------------------- | --------------------------------------------------------------------- |
| **E1** | On a project home, send a message              | Tokens appear progressively, with a caret. Not one block at the end   |
| **E2** | Watch the moment the reply finishes            | **The reply never blanks.** The URL becomes `/t/<id>` a beat later    |
| **E3** | Reload that URL                                | The whole conversation is there                                       |
| **E4** | Send a second message in the same conversation | Continues the SAME thread — no second thread in the rail              |
| **E5** | Press Back                                     | Returns to the project home, not into a redirect loop                 |
| **E6** | Expand "Grounded in N chunks"                  | Real filenames and scores from your uploaded lore                     |
| **E7** | Rename and delete a conversation from the rail | Rail updates; deleting the open one navigates to the project home     |
| **E8** | Create 6+ conversations                        | "Show N more" appears; the open one stays visible even when collapsed |

## Pass F — settings and the persona

| #      | Step                                       | Pass criteria                                                                          |
| ------ | ------------------------------------------ | -------------------------------------------------------------------------------------- |
| **F1** | Open a fresh project's home                | The persona quote is **not blank**, and the eyebrow says `from the preset`             |
| **F2** | Edit the persona, save, return home        | Quote updates; eyebrow now says `you wrote this`                                       |
| **F3** | Change provider/model, then send a message | The per-message footnote names the **new** model                                       |
| **F4** | Add a provider key under **Provider keys** | Listed by hint only. **The key is never echoed back**, and the ellipsis is not doubled |

## Pass G — the actual product (the one that matters)

This is the claim the whole project exists to make. It needs Skyrim and Mantella.

| #      | Step                                                               | Pass criteria                                                                         |
| ------ | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| **G1** | **API keys** → mint a key                                          | Raw key shown **exactly once**, with a copy button                                    |
| **G2** | Copy the Mantella base URL from the card                           | It is `http://127.0.0.1:8000/v1/<key>/<project_id>` — the IP literal, not `localhost` |
| **G3** | Paste into `Documents/My Games/Mantella/config.ini`, launch Skyrim | An NPC answers in character                                                           |
| **G4** | Ask an NPC about a **fact that exists only in your uploaded lore** | It answers from the document. This is the product                                     |
| **G5** | Back in the console, open the project's conversations              | The in-game conversation is there, marked with the NPC's name and the amber dot       |
| **G6** | Revoke the key, talk to the NPC again                              | Fails immediately — revocation is not cached                                          |

> G4 is the only check that proves retrieval, persona and the game path work **together**.
> Invent the fact yourself so it cannot have come from training data.

## Pass H — when things break

| #      | Step                                               | Pass criteria                                                                   |
| ------ | -------------------------------------------------- | ------------------------------------------------------------------------------- |
| **H1** | Stop the backend, click around                     | "Can't reach Sentient" — not a spinner forever, and **never a raw HTTP status** |
| **H2** | Restart it                                         | The app recovers without a manual reload                                        |
| **H3** | Visit `/app/p/does-not-exist`                      | A clean "not found" — **not a 500 page**                                        |
| **H4** | Send a message while a reindex is running          | Amber "your lore is re-embedding", framed as retry-able, not as a failure       |
| **H5** | Clear cookies in another tab, then act in this one | "Your session has expired" as a whole page, with a way back in                  |
| **H6** | Anywhere in the app                                | You never see the words "Unprocessable Content" or a bare status code           |

---

## Before deployment

These are **blocking**, and none is a UI bug. Verified still open on 2026-08-28.

1. **Neon Auth has no trusted domains.**
   `neon neon-auth domain list --branch <branch>` → _"No trusted domains are configured."_
   Local works only because `allow-localhost` is true. **A deployed origin fails every
   sign-in with `INVALID_ORIGIN` until you run:**
   ```bash
   neon neon-auth domain add https://<your-console-origin> --branch <branch>
   ```
2. **`CORS_ALLOW_ORIGINS` does not include the deployed origin.** `api/app.py`'s
   `allow_origin_regex` covers `localhost`/`127.0.0.1` on any port and nothing else.
   Note the ordering constraint in `configure_middleware()`: **CORS must stay the
   outermost middleware**, or a 429 carries no `Access-Control-Allow-Origin` and the
   browser reports it as a network failure with no status at all.
3. **Google's OAuth app is Neon's shared one.** Dev only — it shows Neon's branding.
   Production needs your own client id/secret; see `apps/console/.env.example`.
4. **Three things must name the same branch**: `VITE_NEON_AUTH_URL`, the trusted domain,
   and `DATABASE_URL`. Auth branches _with_ data, so a mismatch signs you into an
   environment whose projects are not there.
5. **Decide the rate limiter and quota.** `RATE_LIMIT_ENABLED` and
   `TOKEN_QUOTA_PER_MONTH` are **OFF by default**. A public origin with an open
   `POST /v1/keys` and no limiter is an open proxy on your provider bill.
   Known gap, stated rather than hidden: the limiter keys on the API key's hash, so
   **ten keys buy ten buckets**. `MAX_API_KEYS_PER_USER` (25) bounds that but does not
   close it.
6. **Run pass G against the deployed origin, not just locally.** It is the only pass
   that exercises the game path, and the game path is the product.

## Known-open — do not file these as bugs

- **A failed reindex is indistinguishable from a queued one.** `reindexing_required` is
  written both by `update_config` ("queued") and by `run_reindex_job`'s `except`
  ("failed"). The console cannot tell them apart because the backend does not carry the
  distinction. Backend item first.
- **A non-streaming provider error reaches Mantella as an opaque 500** with an empty
  body. The streaming path was fixed in `134741e`; this is its sibling.
- **`RAG_SCORE_THRESHOLD` is inert below 0.5 on Qdrant.** It is a cosine floor on FAISS
  but a rank-fusion artefact on Qdrant, where gibberish scores 0.5. Never tune it against
  one backend and deploy the other.
- **On `VECTOR_BACKEND=qdrant`, every tenant shares one embedding dimension.** The shared
  collection is created once at whatever dimension writes first. FAISS has no such limit.
- **LangChain is pinned `<1.0.0`**, which defers 10 advisories. A migration, not an upgrade.
