"""The user credential vault: encrypt, store, list and revoke provider keys.

Takes its collaborators as explicit arguments rather than reaching for the
`api.deps` singletons, which is what makes these callable from somewhere other
than a route handler. Failures are raised as `sentient.core.errors` types; the
router owns the translation to status codes.
"""

from __future__ import annotations

from typing import Any

from sentient.core.crypto import crypto_available, encrypt_key, key_hint
from sentient.core.errors import InvalidRequest, VaultUnavailable

_CREDENTIAL_PROVIDERS = {"google", "openai", "huggingface", "groq", "cerebras", "openrouter"}


def normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized not in _CREDENTIAL_PROVIDERS:
        raise InvalidRequest("unknown provider")
    return normalized


def vault_secret(settings) -> str:
    if not crypto_available(settings):
        raise VaultUnavailable("credential vault is not configured")
    return settings.sentient_secret_key


async def invalidate_user_projects(state_store, runtime_cache, user_id: str) -> None:
    for project in await state_store.list_projects(user_id):
        runtime_cache.invalidate(project["id"])


async def store_credential(
    state_store,
    runtime_cache,
    settings,
    *,
    user_id: str,
    provider: str,
    api_key: str,
) -> dict[str, Any]:
    # Gate on the vault before validating anything else: with no vault
    # configured an unknown provider must still answer 503, not 400.
    secret = vault_secret(settings)
    normalized = normalize_provider(provider)
    try:
        encrypted = encrypt_key(api_key, secret)
    except Exception as exc:
        raise VaultUnavailable("credential vault is unavailable") from exc
    row = await state_store.upsert_credential(
        user_id, normalized, encrypted, key_hint(api_key)
    )
    await invalidate_user_projects(state_store, runtime_cache, user_id)
    return {"provider": row["provider"], "key_hint": row["key_hint"]}


async def list_credentials(state_store, settings, *, user_id: str) -> list[dict[str, Any]]:
    vault_secret(settings)
    return await state_store.list_credentials(user_id)


async def remove_credential(
    state_store,
    runtime_cache,
    settings,
    *,
    user_id: str,
    provider: str,
) -> bool:
    vault_secret(settings)
    deleted = await state_store.delete_credential(user_id, normalize_provider(provider))
    await invalidate_user_projects(state_store, runtime_cache, user_id)
    return deleted
