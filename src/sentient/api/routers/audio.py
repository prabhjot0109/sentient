"""Speech-to-text proxy and its recent-capture diagnostics.

Error translation, preserved exactly from the pre-R9 route body:

    Unauthenticated -> 401 (from the X-API-Key identity check)
    InvalidRequest  -> 400 "No speech-to-text credential available: ..."
    UpstreamFailure -> 502 "{provider} STT failed: {e}"
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
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
    language: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
    response_format: Optional[str] = Form("json"),
    temperature: Optional[float] = Form(0.0),
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """OpenAI-compatible speech-to-text that doubles as a microphone diagnostic.

    NOTE: this is the ONE route where `Authorization: Bearer` is a *provider* key
    rather than a Neon Auth JWT — Mantella's UI has a single field for its Whisper
    credential and forwards it here. It therefore does not use `Depends(deps.current_user)`;
    Sentient identity comes from `X-API-Key` only. Do not "fix" this to match the
    other routes without changing what Mantella sends.

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
            deps.state_store, deps._settings, deps.identity_cache, x_api_key
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
def recent_transcriptions(limit: int = 20):
    """The last few utterances with their measured mic levels, for debugging."""
    return service.recent_history(limit)
