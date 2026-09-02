# Privacy

Last updated: 2026-09-02.

This describes the **hosted** deployment at `sentient-console.vercel.app` and
`sentient-api-54r2.onrender.com`. If you run Sentient yourself, none of the data below reaches the
maintainer — see [SELFHOST.md](SELFHOST.md), and note that in that case *you* are the operator this
document is about.

Everything here was read out of `migrations/*.sql` and `src/sentient/`, not written from memory.

---

## The short version

Sentient stores **your full conversation transcripts** and **your provider API keys, encrypted**.
The game path writes transcripts without the player ever opening a console. Your lore documents and
your conversations are sent to the AI provider you configured. There is no advertising, no
analytics profile, and nothing is sold.

---

## What is stored, table by table

| Table | What is in it |
| --- | --- |
| `users` | Your Neon Auth id (the JWT `sub`), your email address, a creation timestamp |
| `api_keys` | A **SHA-256 hash** of each key you mint, an optional label, a revoked flag. The raw key is shown once at creation and never stored |
| `projects` | Project name, preset, status, and why a rebuild last failed |
| `project_configs` | Your model, provider and retrieval settings, and your project's persona text |
| `documents` | Filename, size, chunk count, ingestion status, for each file you upload |
| `provider_credentials` | Your third-party provider API keys, **encrypted with Fernet**, plus a non-reversible hint (last few characters) so you can tell which key is which |
| `chat_threads` | One row per conversation: an NPC name, the client session token, a title |
| `chat_messages` | **The full text of every message**, yours and the NPC's, with the model used, token counts, and the lore chunks that reply was grounded in |

Alongside the database:

- **Uploaded files themselves** live on the API server's disk under `DATA_DIR`. On the current free
  instance that directory does not survive a restart, so the files are frequently *less* durable
  than the rows describing them.
- **Vector embeddings** of your documents live in Qdrant Cloud, partitioned per user and project.
  An embedding is a numeric representation of your text; it is derived from the text, and text can
  be partially reconstructed from embeddings, so treat it as the document.
- **Server logs** carry a hashed user identifier, project and thread ids, timings, and errors. No
  provider key, no minted API key, no JWT is ever logged. `tests/test_logging.py` enforces the
  absence of `print()` in the server for this reason.

### Two things worth calling out plainly

**Transcripts are written from the game path too.** When Mantella talks to Sentient, both the
player's line and the NPC's reply are persisted, with no console open and no per-turn prompt. That
is a feature — it is what gives an NPC memory across a session — and it is also the largest thing
this service holds about you.

**Retrieved lore is put in the system message.** Your documents speak with the persona's own
authority, which is safe only because you uploaded them yourself.
[SECURITY.md](SECURITY.md) states the full posture.

---

## Who else receives your data

Sentient is a small piece of infrastructure between you and services it does not control.

| Recipient | What they receive | When |
| --- | --- | --- |
| **Your LLM provider** (Google, OpenAI, Groq, Cerebras, OpenRouter, HuggingFace) | The persona, the retrieved lore chunks, and the conversation | Every turn |
| **Your embedding provider** (same list) | The text of every document you upload, in chunks | On upload and on every reindex |
| **Your speech-to-text provider** (Groq, OpenAI, or your own server) | The audio of what you said | Only if you use voice input |
| **Neon** (Postgres + Auth, `ap-southeast-1`) | Everything in the tables above | Continuously |
| **Qdrant Cloud** (`eu-central-1`) | Document embeddings and their chunk text | Continuously |
| **Render** (`singapore`) | Request logs for the API | Continuously |
| **Vercel** | Request logs for the console and the landing site | Continuously |
| **Sentry**, if enabled | Exception reports, with the API key stripped from the URL path and from headers | On an error |
| **Langfuse**, if enabled | Traces of a turn: prompts, replies, latencies, token counts | Every turn |

**Which provider is which is your choice**, and it is the reason the credential vault exists: with
your own key stored, your traffic runs under *your* agreement with that provider. With no stored
key, the deployment's own key is used instead.

Each of these companies has its own privacy policy, and your data is subject to it once it arrives.
This document cannot and does not speak for them.

---

## Encryption, and its exact limits

`provider_credentials.encrypted_key` is encrypted with Fernet (AES-128-CBC with an HMAC) under a
server-side key held in `SENTIENT_SECRET_KEY`, which is never in the database and never in git.
Anyone with database access alone cannot read your provider keys. Anyone with **both** the database
and the server's environment can.

Rotating that key re-encrypts every stored credential in place
(`sentient rotate-secret`, with `SENTIENT_SECRET_KEY_OLD` present for the transition); it does not
invalidate your keys and you do not need to re-enter them.

Everything else — transcripts, documents, personas — is stored **unencrypted at the application
level**. Neon and Qdrant encrypt at rest at the storage level; that protects against a stolen disk,
not against anyone with database credentials.

---

## Deleting things

- **Delete a document** — removes the file, its vectors and its row.
- **Delete a thread** — removes the thread and every message in it.
- **Delete a project** — removes its config, its threads, every message in them, its document rows,
  and its vectors from the vector store. That last part matters more than it sounds: on Qdrant
  every tenant shares one collection, so an orphaned partition would never be reindexed away.
- **Revoke an API key** — the row is kept with `revoked = true`, because a deleted row cannot be
  distinguished from one that never existed, and revoked keys do not count against your key limit.

To delete your account and everything under it, open an issue on the repository. Deletions cascade
from `users`, so removing that row removes all of the above.

There is **no automatic retention limit**. Nothing expires on its own; what you have not deleted is
still there.

---

## What is not done

Stated because a privacy policy that only lists reassurances is not one:

- There is no encryption of transcripts at the application level.
- There is no audit log of administrative access to the database.
- There is no automated data export. Ask, and you get a dump.
- The service is operated by one person, in one country, with no dedicated privacy team, no
  certification and no formal breach-notification SLA.

---

## Contact

Open an issue at <https://github.com/prabhjot0109/sentient/issues> for data questions, deletion
requests, or anything in this document that turns out not to be true.

For a **security vulnerability**, open a private security advisory instead of a public issue — see
[SECURITY.md](SECURITY.md).
