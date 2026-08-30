"""Speech-to-text provider and credential resolution for the STT proxy.

Kept out of ``api.py`` because the provider branching, the model remapping and the
R7 vault lookup are three independent decisions that all have to be made before a
single upstream byte moves, and none of them are HTTP concerns.

Only Groq and OpenAI are handled: they are the two providers Mantella's
speech-to-text dropdown offers, and the only two that serve Whisper.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from sentient.adapters.state.base import StateStore
from sentient.core.config import RAGSettings
from sentient.core.logging import get_logger

log = get_logger(__name__)

GROQ_DEFAULT_MODEL = "whisper-large-v3-turbo"
OPENAI_DEFAULT_MODEL = "whisper-1"

# Sentient's own product keys. They are identity, never LLM/STT credentials, so a
# forwarded one must never reach a provider — see provider_of_key.
SENTIENT_KEY_PREFIX = "sk-sent-"


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token or None


def looks_like_jwt(token: str) -> bool:
    """Whether a bearer token is an identity JWT rather than a provider key.

    Two dots and a ``eyJ`` prefix: a JWT is three base64url segments, and the
    header always begins ``{"alg"`` — which base64url-encodes to ``eyJ``. No
    provider key has that shape, so the check is cheap and one-directional.

    This exists because ``Authorization: Bearer`` means two different things on
    the transcription route. Mantella sends its own Whisper credential there,
    while the console sends a Neon Auth JWT for identity. Telling them apart by
    SHAPE keeps that free: verifying the token to find out would put a JWKS
    round trip on the critical path of every spoken line.
    """
    return token.count(".") == 2 and token.startswith("eyJ")


def provider_of_key(key: str) -> str | None:
    """Which STT provider a raw key belongs to. Only Groq and OpenAI serve Whisper.

    ``sk-sent-…`` is checked before the ``sk-`` branch on purpose: Sentient product
    keys share OpenAI's prefix, and classifying one as an OpenAI credential would
    forward a Sentient identity key to a third party.
    """
    if key.startswith(SENTIENT_KEY_PREFIX) or looks_like_jwt(key):
        return None
    if key.startswith("gsk_"):
        return "groq"
    if key.startswith("sk-"):
        return "openai"
    return None


async def _stored_key(
    state: StateStore | None, settings: RAGSettings, user_id: str | None, provider: str
) -> str | None:
    """The user's R7 vault key for `provider`, or None. Never raises: a bad secret
    must degrade to the env floor rather than take transcription down."""
    # Bound to a local so the None check narrows it for the decrypt call below;
    # getattr keeps working for the test doubles that stand in for RAGSettings.
    secret = getattr(settings, "sentient_secret_key", None)
    if state is None or not user_id or not secret:
        return None
    try:
        from sentient.core.crypto import decrypt_key

        row = await state.get_credential(user_id, provider)
        if not row:
            return None
        return decrypt_key(
            row["encrypted_key"], secret, getattr(settings, "sentient_secret_keys_old", ())
        )
    except Exception as exc:  # no key material in the message
        log.warning(
            "stored STT credential unusable; falling back to env",
            extra={"provider": provider, "reason": type(exc).__name__},
        )
        return None


async def resolve_stt_credential(
    state: StateStore | None,
    settings: RAGSettings,
    *,
    authorization: str | None,
    user_id: str | None,
) -> tuple[str | None, str | None, str]:
    """Pick the upstream provider, the key to call it with, and a log-safe source label.

    Precedence: a forwarded bearer first, then — per provider, Groq before OpenAI —
    the user's stored credential, then the env floor. Mantella already holds a
    Whisper key and forwards it, so honouring that keeps the credential in exactly
    one place when Sentient is used purely as a transcription proxy.

    Groq is tried ahead of OpenAI at every tier rather than "all stored keys before
    all env keys": for Whisper specifically Groq is the faster and cheaper service,
    so an operator's `GROQ_API_KEY` is the better answer than a stored OpenAI key
    that was most likely uploaded for chat completions.

    Returns (None, None, "none") when nothing is available — the caller rejects the
    request rather than building a client that cannot authenticate.
    """
    inbound = bearer_token(authorization)
    if inbound and (inbound.startswith(SENTIENT_KEY_PREFIX) or looks_like_jwt(inbound)):
        # Identity arriving in the credential header -- a Sentient product key, or
        # the console's Neon Auth JWT. Fall through to the vault/env as if no key
        # had been forwarded at all. Dropping it HERE rather than at the first
        # branch matters: the trailing fallback below forwards an unrecognised
        # token to Groq, so leaving `inbound` set would transmit a user's identity
        # token to a third party whenever no vault or env credential resolved.
        inbound = None

    if inbound:
        provider = provider_of_key(inbound)
        if provider:
            return provider, inbound, "Mantella (forwarded)"

    for provider, env_name in (("groq", "GROQ_API_KEY"), ("openai", "OPENAI_API_KEY")):
        stored = await _stored_key(state, settings, user_id, provider)
        if stored:
            return provider, stored, "stored credential"
        env_key = os.getenv(env_name)
        if env_key:
            return provider, env_key, "env"

    # A forwarded key of unknown shape is still worth trying against Groq, the only
    # provider Mantella's dropdown offers alongside OpenAI.
    if inbound:
        return "groq", inbound, "Mantella (forwarded, unrecognised prefix)"
    return None, None, "none"


def upstream_model(provider: str, requested: str) -> str:
    """Remap the model Mantella asked for onto one the resolved provider serves.

    Mantella sends whichever name is set in its UI; Groq serves only the
    `whisper-large-v3` family and 400s on `whisper-1`, while OpenAI 400s on the
    large-v3 names, so a mismatched pair must be corrected rather than forwarded.
    Any other `whisper*` name is passed through to Groq unchanged so a newly
    released model is usable without a code change.
    """
    if provider == "groq":
        return (
            requested if "whisper" in requested and requested != "whisper-1" else GROQ_DEFAULT_MODEL
        )
    return requested if requested.startswith("whisper-1") else OPENAI_DEFAULT_MODEL


@lru_cache(maxsize=4)
def stt_client(provider: str, api_key: str) -> Any:
    """One client per (provider, key), reused across utterances.

    The SDK client owns an HTTP connection pool; building a fresh one per utterance
    throws that pool away and pays a new TCP+TLS handshake to the provider each time.
    Measured: 389ms per transcription with a new client versus 185ms with a reused
    one — over 200ms of pure handshake on the critical path between the player
    finishing a sentence and the NPC answering.

    Imports are deferred so a deployment that never transcribes does not pay either
    SDK's import cost, and neither becomes a hard dependency of `logic`.
    """
    if provider == "groq":
        from groq import Groq

        return Groq(api_key=api_key)

    from openai import OpenAI

    return OpenAI(api_key=api_key)
