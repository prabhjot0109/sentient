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

from sentient.adapters.auth import AuthError, user_key_of
from sentient.adapters.stt import client as stt
from sentient.adapters.stt.diagnostics import analyse_wav, explain_empty_transcription
from sentient.core.errors import InvalidRequest, Unauthenticated, UpstreamFailure
from sentient.core.logging import get_logger

log = get_logger(__name__)

# Keyed by `user_key`, the same tenant id resolve_user hands every other route,
# so a Mantella POST carrying X-API-Key and a console GET carrying a JWT reach one
# bucket for one person. That holds only because user_key is derived from the user
# id rather than the credential (spec G1).
_STT_HISTORY: dict[str, list[dict]] = {}
_STT_HISTORY_LIMIT = 50

# resolve_user's no-credential branch returns this literal as the user_key, so the
# anonymous POST and the anonymous GET have one spelling of "no identity". Without
# a shared literal the single-user local mode records under one name and reads
# under another, and the diagnostic always looks empty.
ANONYMOUS_BUCKET = "default"

_NO_CREDENTIAL = (
    "No speech-to-text credential available: set GROQ_API_KEY or OPENAI_API_KEY "
    "in .env, upload one via POST /v1/credentials, or let Mantella forward its "
    "own key via the Authorization header."
)


def history_bucket(user_id: str | None) -> str:
    """The buffer key for a caller, mirroring resolve_user's two branches."""
    return user_key_of(user_id) if user_id else ANONYMOUS_BUCKET


def record_history(user_key: str, entry: dict) -> None:
    """Append to this caller's buffer only.

    The buffer holds transcribed player speech, so a single shared list meant any
    caller of GET /v1/audio/transcriptions/recent read every tenant's voice input
    (spec A5). Each bucket is bounded independently.
    """
    bucket = _STT_HISTORY.setdefault(user_key, [])
    bucket.append(entry)
    del bucket[:-_STT_HISTORY_LIMIT]


def recent_history(user_key: str, limit: int) -> dict[str, Any]:
    """The last few utterances with their measured mic levels, for debugging."""
    bucket = _STT_HISTORY.get(user_key, [])
    window = bucket[-max(1, min(limit, _STT_HISTORY_LIMIT)) :]
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

    # One buffered record rather than eighteen writes. The block is a single
    # event a person reads top to bottom; emitted line by line, two concurrent
    # spoken lines interleaved into unreadable soup. The measurements themselves
    # are unchanged — they are fitted to real captures.
    block = [
        "=" * 65,
        f"[STT] Mic input received at {timestamp}",
        f"   File     : {filename} ({len(contents) / 1024:.1f} KB)",
    ]
    if report.sample_rate:
        block.append(
            f"   Audio    : {report.duration_s:.2f}s  {report.sample_rate} Hz  "
            f"{report.channels}ch  {report.sample_width * 8}-bit"
        )
        block.append(
            f"   Level    : [{report.level_bar()}] RMS {report.rms * 100:5.2f}%  "
            f"peak {report.peak * 100:5.1f}%"
        )
    block.append(f"   Verdict  : {report.verdict} - {report.detail}")
    block.extend(f"   ! {warning}" for warning in report.warnings)

    if provider is None:
        block.append(f"   [ERROR] {_NO_CREDENTIAL}")
        block.append("=" * 65)
        log.error("\n".join(block))
        raise InvalidRequest(_NO_CREDENTIAL)

    stt_model = stt.upstream_model(provider, model)
    # The key itself is never logged, only where it came from.
    block.append(f"   Upstream : {provider} / {stt_model}  (key from {key_source})")

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
        client = stt.stt_client(provider, api_key, stt.configured_base_url(settings))
        response = await asyncio.to_thread(client.audio.transcriptions.create, **options)
    except Exception as e:
        block.append(f"   [ERROR] {provider} transcription failed: {e}")
        block.append("=" * 65)
        log.error("\n".join(block), exc_info=True)
        record_history(
            history_bucket(user_id),
            {
                "time": timestamp,
                "text": "",
                "error": str(e),
                "provider": provider,
                "model": stt_model,
                "audio": report.as_dict(),
            },
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
        block.append(f'   DISCARDED: "{text}" - hallucinated from {report.verdict.lower()} audio')
        block.append(f"   [WHY] {report.detail}")
        text = ""

    if text:
        block.append(f'   HEARD    : "{text}"   ({elapsed:.2f}s)')
    else:
        block.append(f"   HEARD    : <nothing>   ({elapsed:.2f}s)")
        if not discarded:
            block.append(f"   [WHY] {explain_empty_transcription(report)}")
    block.append("=" * 65)
    log.info("\n".join(block))

    record_history(
        history_bucket(user_id),
        {
            "time": timestamp,
            "text": text,
            "discarded_hallucination": discarded,
            "error": None,
            "provider": provider,
            "model": stt_model,
            "elapsed_s": round(elapsed, 3),
            "audio": report.as_dict(),
        },
    )

    return {"text": text, "report": report, "discarded": discarded, "elapsed": elapsed}
