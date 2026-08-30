"""Speech-to-text proxy and its recent-capture diagnostics.

Error translation, preserved exactly from the pre-R9 route body:

    Unauthenticated -> 401 (from the X-API-Key identity check)
    InvalidRequest  -> 400 "No speech-to-text credential available: ..."
    UpstreamFailure -> 502 "{provider} STT failed: {e}"
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse

from sentient.adapters.stt import client as stt
from sentient.api import deps
from sentient.core.errors import InvalidRequest, Unauthenticated, UpstreamFailure
from sentient.services import transcription as service

router = APIRouter()


@router.post("/v1/audio/transcriptions")
async def audio_transcriptions(
    file: UploadFile = File(...),
    model: str = Form(stt.GROQ_DEFAULT_MODEL),
    language: str | None = Form(None),
    prompt: str | None = Form(None),
    response_format: str | None = Form("json"),
    temperature: float | None = Form(0.0),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """OpenAI-compatible speech-to-text that doubles as a microphone diagnostic.

    NOTE: this is the ONE route where `Authorization: Bearer` can be a *provider*
    key rather than a Neon Auth JWT — Mantella's UI has a single field for its
    Whisper credential and forwards it here. It therefore does not use
    `Depends(deps.current_user)`, which would reject that outright. Do not "fix"
    this to match the other routes without changing what Mantella sends.

    Both meanings are now accepted, told apart by shape rather than by trying a
    verification: a Bearer token with JWT shape is the console's identity, and
    anything else is a Whisper credential to forward upstream. `X-API-Key` still
    carries identity for Mantella. Sending no credential at all remains valid and
    resolves the provider key from the env floor — that is the single-user local
    mode, and it is why identity is resolved rather than required.

    Point Mantella's Speech-to-Text -> Whisper URL at this endpoint and every
    utterance is measured (duration, RMS, peak, clipping) and printed alongside the
    text, which is the only way to tell a dead microphone apart from an STT model
    that simply heard nothing.
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    contents = await file.read()
    filename = file.filename or "audio.wav"

    try:
        user_id = await service.resolve_identity(
            deps.state_store,
            deps._settings,
            deps.identity_cache,
            x_api_key,
            authorization=authorization,
        )
    except Unauthenticated as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    try:
        result = await service.transcribe(
            deps.state_store,
            deps._settings,
            contents=contents,
            filename=filename,
            timestamp=timestamp,
            model=model,
            language=language,
            prompt=prompt,
            temperature=temperature,
            authorization=authorization,
            user_id=user_id,
        )
    except InvalidRequest as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except UpstreamFailure as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    text = result["text"]
    if response_format == "text":
        return PlainTextResponse(text)
    if response_format == "verbose_json":
        return {
            "task": "transcribe",
            "language": language or "auto",
            "duration": round(result["report"].duration_s, 3),
            "text": text,
            "segments": [],
        }
    return {"text": text}


@router.get("/v1/audio/transcriptions/recent")
async def recent_transcriptions(
    limit: int = 20,
    user: tuple[str, str] = Depends(deps.current_user),
):
    """The last few utterances with their measured mic levels, for debugging.

    Scoped to the caller: this buffer echoes transcribed player speech, and a
    single process-wide list let any caller read every tenant's voice input.
    """
    _, user_key = user
    return service.recent_history(user_key, limit)
