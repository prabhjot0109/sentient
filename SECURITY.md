# Security posture

Three risks that have no fix. Each is bounded and stated here rather than relitigated at 2am after
a launch, and each claim below was checked against the code on 2026-08-26 rather than inherited
from a design document.

At the repo root, not under `docs/`, because that directory is deliberately untracked and this is a
user-facing document — and because it is where GitHub looks for it.

## Reporting a vulnerability

Open a private security advisory on the repository rather than a public issue. There is no bounty
and no SLA; this is a single-maintainer project and honesty about that is worth more than a
promise nobody can keep.

---

## S3 — Prompt injection

Sentient's entire value is injecting user-supplied text into a model's prompt. That cannot be
"solved" while the product does what it does. What follows is the blast radius.

### What a malicious document can make an NPC do

- **Say anything, in any voice**, including breaking character and impersonating the system or the
  operator.
- **Contradict the persona and the preset.**
- **Emit text that reads as an instruction to whatever consumes the reply.** For Mantella that is a
  local TTS engine, so the blast radius is *speech*. No consumer in this stack executes the reply.

### What it cannot do

- **Reach another user's or another project's documents.** Every retrieval carries a `user_key` +
  `project_id` filter, and both were probed live from two identities — FAISS in the
  [S1 audit](docs/superpowers/verification/2026-08-26-S1-isolation-audit.md) (2026-08-26), Qdrant
  at the backend seam in the V3 gate (2026-08-25) with the router's ownership check bypassed.
  Frozen as `tests/test_tenant_isolation.py`.
- **Reach the vault.** Credentials are Fernet-encrypted at rest, decrypted only to construct a
  provider client, and never enter a prompt.
- **Cause a tool call or any side effect. There are no tools.** `services/rag.py` and
  `services/chat.py` invoke a chat model with retrieved text and return a string; no `bind_tools`,
  no function calling, no agent loop anywhere in `src/sentient/`.

> **This last sentence is only true while it is true.** If tool use is ever added, this section
> must be rewritten *before* that ships. A tool-calling NPC grounded on user-uploaded text is a
> different product with a different threat model.

### The mitigations that exist, and how weak they are

**Retrieved lore is appended to the *system* message.** `inject_lore`
(`adapters/llm/openai_wire.py:101`) concatenates the lore block onto the existing `SystemMessage`,
directly after the persona that `inject_persona` prepended. So document text does **not** sit in
the user turn where a model would weigh it as untrusted input — it carries the same authority as
the persona itself. There is no privilege boundary between the operator's instructions and the
document's contents, weak or otherwise.

The wrapper text around the lore block ("Never mention these notes and never break character") is
an instruction competing with whatever the document says, in the same message, at the same
authority. It is a hint, not a control.

**The threat model is mostly self-injection.** Documents are per-project and uploaded by the
project's owner, so today the person who can inject is the person who would be fooled. That is the
only reason the paragraph above is tolerable.

**A shared-project feature would change this analysis completely** — it would turn self-injection
into cross-user injection overnight. Anything that lets one user's document reach another user's
NPC needs this section rewritten first, and probably needs lore moved out of the system message.

---

## S5 — The API key in the URL path

The game route is `/v1/<api_key>/<project_id>/chat/completions`. Mantella cannot send headers, so
the key is in the path — where it lands in proxy logs, access logs, and browser history.

The architecture overview documents this as acceptable **for self-hosted**, where the only proxy is
the user's own machine. **That assumption does not survive a hosted deployment.**

### What protects the key today

- `sk-sent-` prefixed and generated with `secrets.token_urlsafe(32)` — 256 bits of entropy
  (`adapters/auth.py:28`).
- **Only the SHA-256 hash is stored.** The raw key is shown once, at creation, and never again.
- **Revocation is immediate**, not eventually-consistent: `DELETE /v1/keys/{id}` clears
  `IdentityCache`, and F7 measured the effect three times with no sleep between them.
- The key selects a *tenant*. It is never a provider credential — `deps._as_provider_key` rejects
  anything starting with `sk-sent-`, so a leaked product key cannot be replayed against Groq or
  Google directly.

### What is missing

- **No expiry.** A key is valid until someone revokes it by hand.
- **No scope.** Every key can do everything its owner can, including minting more keys and reading
  the credential vault's hints.
- **No last-used timestamp**, so a leaked key cannot be identified as the one being abused.
- **No cap on how many a user may hold** — see S6.

### The recommendation for hosted mode

Accept the same key in an `X-API-Key` header as an *alternative* to the path, so a hosted operator
can require the header form and refuse the path form entirely.

**Do not build that here.** Mantella's config supplies a base URL and nothing else, so a header
variant needs a Mantella-side story before it is usable by the client that actually needs it. That
is P3's territory, not this phase's.

---

## S6 — Abuse, scenario by scenario

| Scenario | Control today | Gap |
|---|---|---|
| Upload 10 GB | Streaming per-file cap (`UPLOAD_MAX_BYTES`, 25 MiB) + per-user disk quota (`UPLOAD_USER_QUOTA_BYTES`, 500 MB), both enforced in `services/ingestion.py` where staging already lives | **None for size on the wire.** A 2 MB PDF that expands to 500 MB of extracted text is not bounded — see the finding below. |
| Fifty Mantella instances on one key | `RATE_LIMIT_COMPLETIONS_PER_MINUTE` (30/min), keyed on the API key's hash | Per-process: N replicas means N× the limit until X5. And ten keys buy ten buckets — see the finding below. |
| Mint 10,000 API keys | `RATE_LIMIT_DEFAULT_PER_MINUTE` bounds the *rate*, nothing bounds the *total* | **No per-user key cap** — see the finding below. |
| Burn a stored provider key | `TOKEN_QUOTA_PER_MONTH`, summed from `chat_messages.total_tokens` over a rolling 30 days | Counts only turns Sentient recorded. Embedding spend during ingestion is bounded by disk quota, not tokens. |
| Upload a renamed binary as a PDF | Magic-byte sniffing, separator-agnostic filename sanitisation (H6, pinned by 21 tests in `tests/test_upload_hardening.py`) | None known |
| Sign up 10,000 accounts | Neon Auth's own controls | **Outside this codebase.** Sentient sees a verified `sub` and creates a user row; it has no signup rate limit of its own and cannot have one. |

### Three findings, raised as their own backlog items

Each of these is a change with its own test and its own commit, not a paragraph to fold into a
posture document. Raised in `docs/superpowers/plans/order.md` rather than fixed here — the same
judgement B5 made about the 409 TTL, and it kept both changes reviewable.

1. **A character cap after extraction.** The upload cap counts bytes on the wire; a compressed PDF
   that expands to enormous text passes it and then costs embedding calls per character. Belongs in
   `services/ingestion.py` beside the byte cap. This is the one sub-item of S2 that H6 did not
   close.
2. **A per-user API key cap.** `POST /v1/keys` is open to any authenticated user with no ceiling.
   Roughly four lines in `routers/keys.py`. It is also the complement to the rate limiter's
   identity choice: buckets are keyed on the key's hash, so capping keys caps buckets.
3. **A surfaced reindex failure.** `projects.status = 'reindexing_required'` is written both by
   "a rebuild is queued" and by "a rebuild failed", and the user is shown neither. Not a security
   issue, but it is the same class — a state the system knows and does not say.

---

## What this document does not cover

- **Transport security.** TLS terminates at the platform; nothing in this codebase configures it.
- **The Qdrant deployment's own auth.** The V3 gate ran against local Docker with no API key, so
  TLS and authenticated gRPC are still unexecuted. It rides along with D1.
- **Denial of service beyond the limits above.** One process, one ingest worker; a determined
  attacker inside the rate limits can still make the box slow.
- **Dependency and license risk**, which is
  [S4's audit](docs/superpowers/verification/2026-08-26-S4-dependency-audit.md).
