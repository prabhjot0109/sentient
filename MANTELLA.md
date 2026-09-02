# Sentient for Mantella

Give Skyrim's NPCs a memory of *your* world — a mod's lore, your own campaign notes, a wiki export
— instead of whatever the base model happens to know about Tamriel.

This guide is for people who install mods. You do not need to write code, run a server, or
understand what RAG is.

---

## Read this first, or the rest will confuse you

**`config/config.ini` in the Sentient repository is Mantella's config, not Sentient's.** It is
checked in as a working reference. Sentient never reads it. Mantella reads:

```
Documents\My Games\Mantella\config.ini
```

That is the file you edit. Everything below refers to it.

---

## What you are wiring up

Mantella already accepts any OpenAI-compatible endpoint as its language-model backend. Sentient
*is* one. You point Mantella at Sentient instead of at OpenAI, and Sentient talks to the provider
on your behalf — but first it looks up the passages of your uploaded documents that bear on what
the player just said, and puts them behind the NPC's persona.

Mantella keeps doing its own text-to-speech, and it should: it has real per-character Skyrim voice
models and generates LipGen facial animation locally. **Sentient serves no TTS at all.** Nothing
about your voices changes.

---

## Setup

### 1. Make an account and a project

Go to <https://sentient-console.vercel.app> and sign up. Create a project — one project is one game
world. Pick the **Skyrim** preset; it gives the NPCs a starting voice you can edit later.

### 2. Upload your lore

Drag PDFs or `.txt` files into the project's Documents screen. A modest text file indexes in
seconds.

**A scanned PDF is different and you should know before you wait.** If the pages are images rather
than selectable text, every page has to be read with OCR, and on the free instance that costs
roughly **60 seconds per page** — a 6-page scan measured **15 minutes 51 seconds**. The screen tells
you it is still working. It is not stuck. If you have a choice, upload text.

### 3. Mint an API key and copy the base URL

On the project's API keys screen, create a key. The console then shows you the exact string to
paste. It looks like this:

```
https://sentient-api-54r2.onrender.com/v1/sk-sent-YOURKEY/YOUR-PROJECT-UUID
```

**Do not add `/chat/completions` to the end.** Mantella appends that itself, and a URL that already
has it becomes `/chat/completions/chat/completions` and 404s. This is the single most common
mistake.

The key is shown once. Copy it now.

### 4. Paste it into `config.ini`

In `Documents\My Games\Mantella\config.ini`, under `[LLM]`:

```ini
llm_api = https://sentient-api-54r2.onrender.com/v1/sk-sent-YOURKEY/YOUR-PROJECT-UUID
model = sentient
```

`model` is a label. Sentient picks the actual model from your project's settings, so you change
models in the console rather than here.

Restart Mantella. Talk to an NPC. Ask about something only your documents know.

---

## Running Sentient on your own machine

If you self-host, everything above is the same except the URL:

```ini
llm_api = http://127.0.0.1:8000/v1/sk-sent-YOURKEY/YOUR-PROJECT-UUID
```

**`127.0.0.1`, never `localhost`.** On Windows that one word costs **208 ms on every single
request**, because the server listens on IPv4 and Windows tries IPv6 first and waits for the refusal.
End-to-end, one NPC line went from about 3200 ms to 780 ms on that change alone. It is invisible in
any log, which is why it is worth stating this loudly.

[SELFHOST.md](SELFHOST.md) covers the rest.

---

## The microphone

Sentient can also handle speech-to-text, which is useful mainly because it tells you *why* a
transcription failed instead of silently producing nothing.

Under `[STT]` in `config.ini`:

```ini
external_whisper_service = True
whisper_url = https://sentient-api-54r2.onrender.com/v1/audio/transcriptions
whisper_model_size = whisper-large-v3-turbo
stt_language = en
```

Pin `stt_language` rather than leaving it on auto-detect. Whisper's language detection is unreliable
on the short utterances push-to-talk produces, and a wrong guess returns empty or garbled text
rather than an error.

**Getting your utterances attributed to you.** Mantella sends whatever secret it holds for the
Whisper service as `Authorization: Bearer`, and Sentient reads that slot by shape: an `sk-sent-`
value is treated as *identity* and never forwarded to a provider, anything else as a Whisper
credential to forward. So if you put your Sentient key in the file Mantella reads its secret from,
your own stored provider credential is used and the diagnostics land in your bucket. Without it the
microphone still works — it just runs on the server's key, and the console's panel stays empty
because it shows yours. Which file that is has changed across Mantella versions
(`GPT_SECRET_KEY.txt`, later `secret_keys.json`), so check your own install.

Three backends are available, chosen by the server's `STT_PROVIDER`:

| Backend | When it makes sense |
| --- | --- |
| `groq` | The default hosted choice. Fast and cheap. |
| `openai` | If your key is already there. |
| `custom` | **The lowest-latency option by a wide margin.** Point `STT_BASE_URL` at whisper.cpp running in server mode on the same machine as the game, and the provider network hop leaves the critical path of every spoken line entirely. |

**Every utterance is measured** — duration, RMS, peak, clipping — before it is sent anywhere. Text a
model invents out of silence is discarded rather than handed to an NPC, which is why a mic that is
too quiet produces *nothing* rather than a hallucinated sentence. If you are debugging a mic,
`GET /v1/audio/transcriptions/recent` exists for exactly this and reports what the last few
captures actually contained.

`audio_threshold` in `[STT]` is Mantella's own gate and applies before any of that.

---

## The persona

Each project has **one** persona — the voice every NPC in that world speaks with — and you edit it
in the console's project settings. It is per game, not per NPC; Mantella supplies the character's
name and Sentient supplies the world's voice.

A project that has never had one edited still speaks in character, from the preset. The console
shows which of the two you are looking at, so you do not overwrite a working voice with a blank box.

Keep it short and keep two rules: **never mention the real world**, and **one to three spoken
sentences**. A long persona does not make a better character; it makes a slower one, and Mantella is
already trimming replies to `max_response_sentences_single`.

---

## Troubleshooting, by symptom

### The NPC does not reply at all

1. **Check the base URL.** Nine times out of ten it ends in `/chat/completions` and should not, or
   the project id is missing. The console prints the correct string; paste it again rather than
   retyping it.
2. **Check your provider.** A dead, expired or unfunded provider key is the most common real cause.
   Mantella now receives an OpenAI-shaped `error` frame rather than silence, so its log carries the
   provider's own words — a 401 or a 402 from Groq or Google says so in plain English.
3. **Is the project rebuilding?** Changing the embedding model in project settings re-indexes
   everything and the chat path answers **409** until it finishes. That is usually seconds. If the
   console shows a red banner instead of an amber one, the last rebuild *failed* and it tells you
   why.
4. **Cold start.** The free instance sleeps after about 15 minutes idle and takes about **6
   seconds** to wake. The first line after a break is slow; the second is not.

### The reply is slow

- **Are you on `localhost`?** See above: 208 ms per request on Windows, for nothing.
- **Reasoning models are a trap for this.** `openai/gpt-oss-20b` measured **583 ms** to first token
  against **146 ms** for `llama-3.1-8b-instant`, because it writes out a chain of thought before
  saying anything aloud. For NPC dialogue, pick a non-reasoning model.
- **The free instance is 0.15 CPU.** It is behind every slow number in this file.

### The NPC answered something I never uploaded

That is the base model talking, and it means retrieval found nothing to use. Check that your
documents show **ready** in the console, not `failed` or `processing`. A scanned PDF that ingested
without OCR available produces zero text while reporting success — the ingestion log distinguishes
those two, and a document with 0 chunks is the tell.

Nothing about grounding is absolute: the model can still invent around what it read.
[SECURITY.md](SECURITY.md) states the bounds honestly.

### The NPC answered something I never said

Almost always the microphone. A quiet or clipped capture makes a speech model produce plausible
sentences out of noise. Sentient discards text it judges to be invented from silence, so what you
usually get is nothing rather than nonsense — and `GET /v1/audio/transcriptions/recent` shows the
waveform measurements that led to the decision.

If it happens with typed input, the NPC is reading a document you uploaded. Retrieved lore is placed
in the system message and speaks with the persona's authority; that is the design, and it is why you
should only upload documents you trust.

---

## Where to report a problem

<https://github.com/prabhjot0109/sentient/issues>

Pick **My NPC won't talk**. It asks for the five things that would otherwise cost a round trip:
which origin you are on, whether you are self-hosting, which provider, whether the project was
rebuilding, and the last few lines of Mantella's log. Filling those in usually gets an answer in one
reply instead of three.

**Redact your key before you paste a log.** It is inside the base URL, so it is in the log. If you
have already posted one, revoke that key in the console — it stops working immediately.

For a security problem, open a private advisory rather than an issue.

---

## A note on the key in the URL

The base URL contains your API key, so it can appear in proxy and access logs.

Mantella *does* send a header — whatever secret it holds goes out as `Authorization: Bearer`, which
is how the microphone path already attributes utterances to you. What no header can carry is the
**project id**, and that is the part that selects your persona, your lore and your transcripts. One
base URL and one model name are the only free-text fields Mantella offers, so the key stays in the
path until a key can name a default project on its own. [SECURITY.md](SECURITY.md) works through
that in full.

The practical consequence for you: **treat these keys as disposable.** Mint one per machine, and
revoke one you have pasted anywhere public. You can hold 25 live keys and revoking is how you make
room. Revocation takes effect immediately, not eventually.
