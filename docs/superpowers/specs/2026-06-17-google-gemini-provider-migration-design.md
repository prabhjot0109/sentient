# Design: Replace OpenRouter with Google Gemini (HuggingFace fallback)

## Problem

`config.py`'s `resolve_provider` defaults embeddings to OpenRouter whenever an
OpenRouter key is present, but OpenRouter has no embeddings endpoint — the
documented default setup is broken. The fix is to drop OpenRouter entirely and
make Google Gemini the primary hosted provider for both chat and embeddings,
with HuggingFace as a key-optional fallback for both.

## Provider model

`Provider` (`logic/config.py`) changes from
`Literal["openrouter", "openai", "huggingface"]` to
`Literal["google", "openai", "huggingface"]`.

- `google` — new primary hosted provider (chat + embeddings), requires
  `GOOGLE_API_KEY`.
- `huggingface` — universal fallback. Embeddings run locally
  (`BAAI/bge-base-en-v1.5`, unchanged), no key ever required. Chat runs via
  HuggingFace's hosted inference router and works keyless (rate-limited) or
  with `HUGGINGFACEHUB_API_TOKEN`/`HF_TOKEN`.
- `openai` — kept as an explicit, non-default opt-in for back-compat
  (`LLM_PROVIDER=openai` / `EMBEDDING_PROVIDER=openai`). Removed from
  auto-detection.
- OpenRouter is deleted: `OPENROUTER_BASE_URL`, `is_openrouter_key`, and every
  OpenRouter-specific branch/env var/doc/UI string.

## Auto-resolution order

`resolve_provider(preferred, *, api_key, fallback)` keeps its shape (explicit
`preferred` short-circuits; otherwise inspect `api_key` then env), but the
detection chain becomes:

1. Pasted `api_key` prefix: `AIza` → `google`; `hf_` → `huggingface`; any
   other non-empty value → `openai` (back-compat for a raw OpenAI key pasted
   into the single frontend key field).
2. Env fallback: `GOOGLE_API_KEY` → `google`; else `OPENAI_API_KEY` →
   `openai`; else `HUGGINGFACEHUB_API_TOKEN` or `HF_TOKEN` → `huggingface`.
3. Otherwise → `huggingface` (the `fallback` parameter passed by
   `load_rag_settings` for both the LLM and embedding resolution calls).

This is used independently for `llm_provider` and `embedding_provider`, same
as today.

## Embeddings (`logic/ingestion.py: build_embeddings`)

Add a `google` branch using
`GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=api_key)`.
`huggingface` and `openai` branches are unchanged. Default model names
(`logic/config.py`):

```
{
  "google": "models/gemini-embedding-001",
  "openai": "text-embedding-3-small",
  "huggingface": "BAAI/bge-base-en-v1.5",
}
```

## Chat model (`logic/rag_engine.py`)

Replace the hardcoded `ChatOpenAI` construction with a per-provider dispatch
(new `build_chat_model` helper, mirroring `build_embeddings`):

- `google` → `ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key, timeout=...)`
- `huggingface` → `ChatHuggingFace(llm=HuggingFaceEndpoint(repo_id=model_name, huggingfacehub_api_token=api_key, timeout=...))` — `api_key` may be `None`.
- `openai` → existing `ChatOpenAI(model=model_name, api_key=api_key, base_url=base_url, timeout=...)`

Default model names:

```
{
  "google": "gemini-2.5-flash",
  "openai": "gpt-4o-mini",
  "huggingface": "Qwen/Qwen2.5-7B-Instruct",
}
```

`base_url` is only meaningful for `openai` going forward; `google` and
`huggingface` ignore it.

The current guard in `NPCBrain.__init__` —
`if not self.settings.llm_api_key: raise ValueError(...)` — only applies when
`llm_provider in ("google", "openai")`. `huggingface` is allowed to proceed
with `llm_api_key is None` (anonymous hosted inference).

## Key handling

The single frontend "API key" field (`settings-dialog.tsx`) keeps its current
shape — one string, no provider selector — but its label/placeholder/help
text change from "OpenRouter / OpenAI API Key" / `sk-...` to
"Google Gemini API Key" / `AIza...`. The backend's prefix sniffing (above)
keeps this working without any new UI controls.

## Dependencies

Add `langchain-google-genai` to `pyproject.toml`. `langchain-huggingface` and
`langchain-openai` are already present and sufficient for the other two
branches.

## Touchpoints (besides the files above)

- `api.py`: lines 36 and 308 check `OPENROUTER_API_KEY`/`OPENAI_API_KEY` for
  the default/global brain — extend to `GOOGLE_API_KEY` first, drop
  `OPENROUTER_API_KEY`.
- `run_rag.py`: same env-var check pattern, same fix.
- `.env.example`, `frontend/.env.example`: replace `OPENROUTER_API_KEY` /
  `OPENROUTER_BASE_URL` with `GOOGLE_API_KEY` (+ optional
  `HUGGINGFACEHUB_API_TOKEN`).
- `README.md`: tech-stack bullet, feature bullet, setup instructions, and the
  "backend defaults to OpenRouter..." paragraph all need rewriting to describe
  Google Gemini primary / HuggingFace fallback, OpenRouter removed.
- `frontend/src/components/chat/chat-container.tsx:122`: empty-state copy
  ("Add your OpenRouter or OpenAI API key...") updated to Google Gemini.

## Tests (`tests/test_rag_pipeline.py`)

- Replace `test_openrouter_settings_enable_openrouter_embeddings_and_llm` with
  a Google-key equivalent: setting `GOOGLE_API_KEY` resolves both providers to
  `google` with the new default model names.
- Add a no-key regression test: with no provider keys set in the environment,
  both `llm_provider` and `embedding_provider` resolve to `huggingface`.
- `test_upload_retrieve_and_delete_pipeline` and
  `test_chat_history_falls_back_to_local_store` are provider-agnostic
  (they patch `build_embeddings` directly / don't touch the LLM) and need no
  changes.

## Out of scope

- No new frontend provider selector — the single-key-field UX is unchanged.
- No change to the FAISS-index-not-committed issue or the full-rebuild-on-
  every-upload issue raised in the earlier review — those are separate from
  the provider migration.
- No live network verification that `models/gemini-embedding-001` /
  `gemini-2.5-flash` / `Qwen/Qwen2.5-7B-Instruct` are exactly correct model
  identifiers against current hosted APIs (no network access in this
  environment) — these are configurable via existing `MODEL_NAME` /
  `EMBEDDING_MODEL_NAME` env vars if a name needs correcting after a live
  test.
