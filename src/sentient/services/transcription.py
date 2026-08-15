"""Speech-to-text: resolve a credential, call upstream, and measure the audio.

The measurement half is not incidental. Mantella forwards every spoken line
here, and without the waveform report there is no way to tell a dead microphone
apart from an STT model that genuinely heard nothing — both look like an empty
string. Worse, Whisper-class models *invent* text from silence, so a hallucinated
line would reach the NPC as though the player had spoken it. `carries_no_speech`
is what stops that.
"""

from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Any

from sentient.adapters.auth import AuthError
from sentient.adapters.stt import client as stt
from sentient.adapters.stt.diagnostics import analyse_wav, explain_empty_transcription
from sentient.core.errors import InvalidRequest, Unauthenticated, UpstreamFailure

_STT_HISTORY: list[dict] = []
_STT_HISTORY_LIMIT = 50

_NO_CREDENTIAL = (
    "No speech-to-text credential available: set GROQ_API_KEY or OPENAI_API_KEY "
    "in .env, upload one via POST /v1/credentials, or let Mantella forward its "
    "own key via the Authorization header."
)


def record_history(entry: dict) -> None:
    _STT_HISTORY.append(entry)
    del _STT_HISTORY[:-_STT_HISTORY_LIMIT]


def recent_history(limit: int) -> dict[str, Any]:
    """The last few utterances with their measured mic levels, for debugging."""
    window = _STT_HISTORY[-max(1, min(limit, _STT_HISTORY_LIMIT)) :]
    return {
        "count": len(window),
        "empty_transcriptions": sum(1 for item in window if not item["text"]),
        "transcriptions": list(reversed(window)),
    }


async def resolve_identity(state_store, settings, identity_cache, x_api_key):
    """Sentient identity for this request, or None when no key was sent."""
    if not x_api_key:
        return None
    try:
        from sentient.adapters.auth import resolve_user

        user_id, _ = await resolve_user(
            state_store, settings, api_key=x_api_key, cache=identity_cache
        )
    except AuthError as e:
        raise Unauthenticated(str(e)) from e
    return user_id


async def transcribe(
    state_store,
    settings,
    *,
    contents: bytes,
    filename: str,
    timestamp: str,
    model: str,
    language: str | None,
    prompt: str | None,
    temperature: float | None,
    authorization: str | None,
    user_id: str | None,
) -> dict[str, Any]:
    """Measure the capture, transcribe it upstream, and drop hallucinated text.

    Returns the text plus everything the route needs to render any of the three
    supported response formats.
    """
    # numpy work on a multi-second capture: cheap (~1ms) but still CPU, and this
    # route is on the critical path of every spoken line.
    report = await asyncio.to_thread(analyse_wav, contents)

    provider, api_key, key_source = await stt.resolve_stt_credential(
        state_store, settings, authorization=authorization, user_id=user_id
    )

    print("\n" + "=" * 65)
    print(f"[STT] Mic input received at {timestamp}")
    print(f"   File     : {filename} ({len(contents) / 1024:.1f} KB)")
    if report.sample_rate:
        print(
            f"   Audio    : {report.duration_s:.2f}s  {report.sample_rate} Hz  "
            f"{report.channels}ch  {report.sample_width * 8}-bit"
        )
        print(
            f"   Level    : [{report.level_bar()}] RMS {report.rms * 100:5.2f}%  "
            f"peak {report.peak * 100:5.1f}%"
        )
    print(f"   Verdict  : {report.verdict} - {report.detail}")
    for warning in report.warnings:
        print(f"   ! {warning}")

    if provider is None:
        print(f"   [ERROR] {_NO_CREDENTIAL}")
        print("=" * 65 + "\n")
        raise InvalidRequest(_NO_CREDENTIAL)

    stt_model = stt.upstream_model(provider, model)
    # The key itself is never logged, only where it came from.
    print(f"   Upstream : {provider} / {stt_model}  (key from {key_source})")

    # The SDKs serialise an explicit None, so optional fields are only sent when set.
    options: dict[str, Any] = {
        "file": (filename, contents),
        "model": stt_model,
        "response_format": "json",
        "temperature": temperature or 0.0,
    }
    if language and language not in ("default", "auto"):
        options["language"] = language
    if prompt:
        options["prompt"] = prompt

    started = perf_counter()
    try:
        # The SDK call is blocking; running it inline would stall the event loop for
        # the whole upload + transcription, starving every other tenant's turn.
        client = stt.stt_client(provider, api_key)
        response = await asyncio.to_thread(client.audio.transcriptions.create, **options)
    except Exception as e:
        print(f"   [ERROR] {provider} transcription failed: {e}")
        print("=" * 65 + "\n")
        record_history(
            {
                "time": timestamp,
                "text": "",
                "error": str(e),
                "provider": provider,
                "model": stt_model,
                "audio": report.as_dict(),
            }
        )
        raise UpstreamFailure(f"{provider} STT failed: {e}") from e

    elapsed = perf_counter() - started
    text = str(getattr(response, "text", response) or "").strip()

    discarded = ""
    if text and report.carries_no_speech:
        discarded = text
        # The waveform holds no speech, so this text was invented by the model.
        # Dropping it makes Mantella report "could not detect speech" and replay the
        # cue, instead of the NPC answering a line the player never spoke.
        print(f'   DISCARDED: "{text}" - hallucinated from {report.verdict.lower()} audio')
        print(f"   [WHY] {report.detail}")
        text = ""

    if text:
        print(f'   HEARD    : "{text}"   ({elapsed:.2f}s)')
    else:
        print(f"   HEARD    : <nothing>   ({elapsed:.2f}s)")
        if not discarded:
            print(f"   [WHY] {explain_empty_transcription(report)}")
    print("=" * 65 + "\n")

    record_history(
        {
            "time": timestamp,
            "text": text,
            "discarded_hallucination": discarded,
            "error": None,
            "provider": provider,
            "model": stt_model,
            "elapsed_s": round(elapsed, 3),
            "audio": report.as_dict(),
        }
    )

    return {"text": text, "report": report, "discarded": discarded, "elapsed": elapsed}
