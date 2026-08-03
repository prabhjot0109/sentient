# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Sentient is a RAG backend that grounds AI NPC dialogue in uploaded game lore (PDF/TXT → FAISS). It serves **two very different consumers** from one FastAPI app, and most confusion in this codebase comes from conflating them:

| Consumer | Endpoint | Who owns the persona | Code path |
| --- | --- | --- | --- |
| React frontend (`frontend/`) | `POST /v1/chat` | **Sentient** — persona is LLM-inferred from the corpus and baked into the system prompt | `NPCBrain` → `create_stuff_documents_chain` |
| Mantella (Skyrim mod) & other OpenAI clients | `POST /v1/chat/completions` | **The caller** — Sentient only appends retrieved lore to the caller's system prompt | bypasses `NPCBrain` entirely; `build_chat_model` + `logic/openai_adapter.py` |

The Mantella path never refuses and never gates: `inject_lore()` augments the caller's messages, and an empty retrieval still produces a reply. Do not add "I don't know" behaviour to that path.

## Commands

```bash
uv sync                                   # install (Python >=3.12)
uv run uvicorn api:app --reload           # backend on :8000
uv run python -m unittest discover -s tests   # full test suite (stdlib unittest; no pytest)
uv run python -m unittest tests.test_rag_pipeline.AudioDiagnosticsTests.test_healthy_utterance_is_ok  # one test
uv run python run_rag.py                  # CLI smoke test: rebuild index, retrieve, generate — no server

cd frontend && npm install && npm run dev # UI on :5173 (Vite bumps the port if taken)
cd frontend && npm run build              # tsc -b && vite build
cd frontend && npm run lint               # eslint
```

## Architecture

### Provider resolution (`logic/config.py`)

Six providers: `google`, `openai`, `huggingface`, `groq`, `cerebras`, `openrouter`. `groq`/`cerebras`/`openrouter` are **chat-only** — if one auto-resolves for embeddings, `load_rag_settings` silently swaps in local HuggingFace embeddings (no key needed).

`resolve_provider` sniffs API-key prefixes (`AIza`→google, `gsk_`→groq, `sk-or-`→openrouter *before* the generic `sk-`→openai, `csk-`→cerebras, `hf_`→huggingface). `provider_api_key` only accepts a client-supplied override when the prefix matches that provider — this is what lets one process run Google embeddings **and** a Groq LLM simultaneously. When touching key handling, preserve that: multiple keys coexisting is a supported configuration, not an accident.

`openai`/`cerebras`/`openrouter` all go through `ChatOpenAI`, differing only by `base_url`.

### Index and manifest coherence (`logic/ingestion.py`)

The FAISS index carries a `manifest.json` recording `embedding_provider`, `embedding_model`, `chunk_size`, `chunk_overlap`, the source list, and the inferred `persona`. `load_index()` returns `None` whenever the manifest doesn't match current runtime settings, which silently triggers a full rebuild. **Changing `EMBEDDING_MODEL_NAME` or the chunk settings therefore re-embeds everything on the next request** — expect latency and API spend.

Three write paths, deliberately distinct:
- `add_file` — embeds only the new file and `merge_from`s it (uploads don't get slower as the corpus grows)
- `remove_file` — deletes that source's vector IDs in place (no re-embedding of survivors)
- `rebuild_index` — full rebuild; builds the new index *before* deleting the old one so a mid-way failure leaves the working index intact

The FAISS merge/save step is serialized by a module-level `_INDEX_WRITE_LOCK` because uploads run in worker threads (`asyncio.to_thread` in `api.upload_file`) and several `ArchivesIngestion` instances can point at the same `index_path`.

`invalidate_cache()` exists because `api.py` writes through `get_default_archives()` while a long-lived `NPCBrain` holds *its own* `ArchivesIngestion`; without dropping the cached handle, `refresh_knowledge()` is a no-op. There is a regression test for exactly this (`test_refresh_knowledge_reflects_uploads_and_deletes_from_another_instance`).

### Caching and process-global state (`api.py`)

`brain` + `brain_key` are module globals: the brain is rebuilt only when the *client-supplied* key changes (env-driven = `None`). `build_chat_model`, `build_embeddings`, `get_default_archives`, and `get_local_chat_store` are all `lru_cache`d — tests must call `.cache_clear()` when patching them.

### Chat history

Supabase if `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` are both set, otherwise SQLite at `data/chat_sessions.db`. `has_supabase_chat_store()` is checked per request, so switching needs no restart. `SQLiteChatStore` deliberately mirrors the Supabase record shape (`messages` as JSON) so `serialize_session_*` is storage-agnostic.

### STT proxy (`/v1/audio/transcriptions`, `logic/audio_diagnostics.py`) — **off by default**

Sentient can stand in front of Groq/OpenAI Whisper so every utterance is measured (duration, RMS, peak, clipping) and printed — Mantella's own "Could not detect speech" warning cannot distinguish a dead mic from a model that heard nothing.

**Mantella no longer routes its microphone here.** `whisper_url` points straight at Groq; point it back at `http://localhost:8000/v1/audio/transcriptions` when you need the mic diagnostics. The proxy used to earn its place on the hot path by letting `prefetch_lore` embed the transcript while Mantella assembled its prompt, hiding a ~511ms Google embedding call. Embeddings now run locally in ~48ms, so that head start is worth less than the hop costs — the proxy's own overhead is real but tiny (`analyse_wav` measures 1.2ms on a 3s 16kHz capture).

Two behaviours worth preserving:
- **Hallucination discard** — when `AudioReport.carries_no_speech` (verdict `SILENT`/`VERY_QUIET`), any returned text is dropped. Whisper reliably invents "Thank you." from silence; letting that through makes the NPC answer a line the player never spoke.
- **Diagnostics never block STT** — unparseable payloads degrade to `UNREADABLE`, which is treated as speech-plausible.

Thresholds (`SILENT_PEAK`, `QUIET_RMS`, …) were fitted to real captures: failures measured 0.000–0.010 RMS, successes 0.120–0.209. Don't retune them without new measurements.

The `groq` SDK is imported lazily inside the handler and is only available transitively via `langchain-groq`.

## Gotchas

- **`config/config.ini` is Mantella's config, not Sentient's.** It's checked in as the reference wiring: `llm_api` → `http://localhost:8000/v1`, `whisper_url` → `Groq` (direct, *not* through Sentient), plus hand-tuned STT values with comments explaining why. Sentient itself is configured purely through `.env`. **Editing this file changes nothing** — Mantella reads `Documents/My Games/Mantella/config.ini`; keep the two in sync by hand.
- **Never point a client at `http://localhost:8000` on Windows — use `http://127.0.0.1:8000`.** Uvicorn binds IPv4 only; Windows resolves `localhost` to `::1` first, so every connection stalls on a refused IPv6 attempt before falling back. Measured here: **208ms connect via `localhost` versus 0.8ms via `127.0.0.1`**, paid per request, before any work happens. End-to-end streaming TTFT for one NPC line went from ~3200ms to ~780ms on this change alone — it dwarfed every other optimisation on this path, and it is invisible in the server's own logs because the server never sees the wasted time. Both `llm_api` in `config/config.ini` and any curl/benchmark must use the numeric address.
- **Latency is dominated by two hops, both measured** (`groq/llama-3.1-8b-instant`, this box): query embedding and LLM time-to-first-token. Embeddings are local (`BAAI/bge-base-en-v1.5`, ~48ms) precisely because the Google round trip was ~511ms; the FAISS search they feed is 0.2ms, so the embedding *is* the retrieval cost. Reasoning LLMs are the other trap — `openai/gpt-oss-20b` measured 583ms TTFT versus 146ms for `llama-3.1-8b-instant`, because it emits a whole chain-of-thought before the first spoken word. Re-measure before changing either; `.env` carries the current numbers.
- **The local embedding model costs ~7s to load and is warmed at startup** by `_warm_grounding_path()` in `api.py`'s lifespan, which runs a real retrieval through `get_default_archives()` — the same instance `/v1/chat/completions` uses, and a *different* one from the brain's. Warming the brain alone leaves the Mantella path cold. Changing `EMBEDDING_MODEL_NAME` re-embeds the whole corpus on next start (~110s for 96 chunks, local, one-off).
- **Tests read the developer's real `.env`** (`load_dotenv()` runs at `logic/rag_engine.py` import). With the checked-in `.env`, 4 of 35 tests fail — three because they assert default provider resolution, and `test_upload_retrieve_and_delete_pipeline` because the score threshold filters out `FakeEmbeddings`' chunks. `test_google_provider_constructs_chat_google_generative_ai` is separately stale: `build_chat_model` now also passes `thinking_budget=0` and `max_retries=2`. These are environment/staleness artifacts, not regressions — verify against a clean env before chasing them.
- `RAG_SCORE_THRESHOLD` only applies on the grounding path used by `/v1/chat/completions`, not to `/v1/retrieve` or the frontend chat.
- Per-provider latency workarounds live in `build_chat_model` and are intentional: Gemini gets `thinking_budget=0`, Groq forwards reasoning params **only when set** (Groq 400s if they're sent to a non-reasoning model), and every provider gets `max_retries=2` so a spent quota fails fast instead of backing off for a minute.
- Scanned PDFs go through OCR only if the Tesseract **binary** is installed (`TESSERACT_CMD` if off `PATH`). Missing OCR logs a warning and ingests empty rather than failing.
- CORS is an origin *regex* (`http://(localhost|127.0.0.1):\d+`) because Vite bumps ports; don't replace it with a fixed list.
- `npc_brain.py` is a two-line re-export of `logic.rag_engine.NPCBrain`; the real class lives in `logic/`.
