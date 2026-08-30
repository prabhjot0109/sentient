"""Speech-to-text provider and credential resolution for the STT proxy.

Kept out of ``api.py`` because the provider branching, the model remapping and the
R7 vault lookup are three independent decisions that all have to be made before a
single upstream byte moves, and none of them are HTTP concerns.

Only Groq and OpenAI are handled: they are the two providers Mantella's
speech-to-text dropdown offers, and the only two that serve Whisper.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from sentient.adapters.state.base import StateStore
from sentient.core.config import RAGSettings
from sentient.core.logging import get_logger

log = get_logger(__name__)

GROQ_DEFAULT_MODEL = "whisper-large-v3-turbo"
OPENAI_DEFAULT_MODEL = "whisper-1"
CUSTOM_DEFAULT_MODEL = "whisper-1"


@dataclass(frozen=True)
class SttProvider:
    """One transcription backend: where its key lives and what it calls its models."""

    name: str
    env_var: str
    default_model: str
    key_prefixes: tuple[str, ...] = ()
    # whisper.cpp in server mode authenticates nothing, so a key cannot be
    # required of every backend.
    requires_key: bool = True
    # `custom` is only a provider once someone says where it lives.
    requires_base_url: bool = False


# Order matters: this is the fallback sequence when nothing is explicitly
# selected. Groq leads because for Whisper specifically it is the faster and
# cheaper service, and `custom` trails because it is opt-in by definition.
PROVIDERS: tuple[SttProvider, ...] = (
    SttProvider("groq", "GROQ_API_KEY", GROQ_DEFAULT_MODEL, ("gsk_",)),
    SttProvider("openai", "OPENAI_API_KEY", OPENAI_DEFAULT_MODEL, ("sk-",)),
    SttProvider(
        "custom",
        "STT_API_KEY",
        CUSTOM_DEFAULT_MODEL,
        requires_key=False,
        requires_base_url=True,
    ),
)

PROVIDERS_BY_NAME = {provider.name: provider for provider in PROVIDERS}

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


def configured_base_url(settings: RAGSettings) -> str | None:
    """Where a self-hosted OpenAI-compatible transcription server lives, if any.

    Read through `getattr` because the test doubles that stand in for RAGSettings
    are SimpleNamespaces, matching how `_stored_key` reads the vault secret.
    """
    return getattr(settings, "stt_base_url", None) or os.getenv("STT_BASE_URL")


async def _credential_for(
    provider: SttProvider,
    state: StateStore | None,
    settings: RAGSettings,
    user_id: str | None,
    base_url: str | None,
) -> tuple[str, str] | None:
    """(key, log-safe source) for one provider, or None when it cannot be used.

    Per-provider, and that ordering is load-bearing: the caller walks providers
    and asks each for its stored key BEFORE its env key, so a stored OpenAI key
    does not beat the server's Groq key. Flattening this to
    all-stored-then-all-env would silently change which account gets billed.
    """
    if provider.requires_base_url and not base_url:
        return None
    stored = await _stored_key(state, settings, user_id, provider.name)
    if stored:
        return stored, "stored credential"
    env_key = os.getenv(provider.env_var)
    if env_key:
        return env_key, "env"
    if not provider.requires_key:
        # A keyless local server. The empty string is a real answer here, not a
        # missing one, so it must not be confused with "nothing resolved".
        return "", f"custom endpoint ({base_url})"
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

    base_url = configured_base_url(settings)
    selected = getattr(settings, "stt_provider", None) or os.getenv("STT_PROVIDER")

    if selected:
        chosen = PROVIDERS_BY_NAME.get(selected.strip().lower())
        # An unknown name is a typo, not a backend. Fall through to the normal
        # order so a mistyped knob degrades to today's behaviour rather than
        # taking transcription down.
        if chosen:
            found = await _credential_for(chosen, state, settings, user_id, base_url)
            if found:
                return chosen.name, found[0], found[1]
            # Deliberately NOT falling through. An explicit selection that
            # silently resolved to a different provider is the failure V1
            # recorded when a harness quietly picked another embedding
            # provider than the server: it works, bills the wrong account,
            # and reads as correct. The caller turns this into a 400 naming
            # what is missing.
            return None, None, "none"

    # `candidate`, not `provider`: the name is already bound above to the
    # provider_of_key result, which is a str.
    for candidate in PROVIDERS:
        found = await _credential_for(candidate, state, settings, user_id, base_url)
        if found:
            return candidate.name, found[0], found[1]

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
    if provider == "custom":
        # No remapping. A self-hosted server names its models whatever it likes
        # ("ggml-large-v3", a filesystem path), so any correction we invented here
        # would be a guess that breaks a working deployment.
        return requested
    if provider == "groq":
        return (
            requested if "whisper" in requested and requested != "whisper-1" else GROQ_DEFAULT_MODEL
        )
    return requested if requested.startswith("whisper-1") else OPENAI_DEFAULT_MODEL


@lru_cache(maxsize=8)
def stt_client(provider: str, api_key: str, base_url: str | None = None) -> Any:
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

    # One SDK covers both "openai" and "custom": every backend worth adding here
    # serves OpenAI-shaped `/v1/audio/transcriptions`, so a new provider is a
    # registry entry and a base URL rather than a new dependency and a new set of
    # failure modes. `base_url=None` is the SDK's own default, so OpenAI proper is
    # unaffected. The placeholder key is for keyless local servers: the SDK
    # refuses to construct without one, and whisper.cpp ignores whatever it gets.
    return OpenAI(api_key=api_key or "not-needed", base_url=base_url)
