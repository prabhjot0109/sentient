"""The user credential vault: encrypt, store, list and revoke provider keys.

Takes its collaborators as explicit arguments rather than reaching for the
`api.deps` singletons, which is what makes these callable from somewhere other
than a route handler. Failures are raised as `sentient.core.errors` types; the
router owns the translation to status codes.
"""

from __future__ import annotations

from typing import Any

from sentient.core.crypto import crypto_available, encrypt_key, key_hint, rotate_token
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
    row = await state_store.upsert_credential(user_id, normalized, encrypted, key_hint(api_key))
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


async def rotate_vault_keys(state_store, settings) -> dict[str, Any]:
    """Re-encrypt every stored credential under the current `SENTIENT_SECRET_KEY`.

    Step 2 of the three-step rotation (README, "Rotating the vault key"). Step 1
    deployed the new key with the old one in `SENTIENT_SECRET_KEY_OLD`, so every
    row still decrypts and new writes already use the new key; this walks the
    table so step 3 can drop the old key without stranding anything.

    **Refuses to run without an old key**, which is the guard that matters. The
    dangerous order is changing `SENTIENT_SECRET_KEY` and running this *before*
    setting `SENTIENT_SECRET_KEY_OLD`: every row would fail to decrypt and the
    command would report a long list of failures that an operator could easily
    read as "already done".

    **Idempotent enough to re-run**, because operators re-run commands.
    `MultiFernet.rotate` decrypts then re-encrypts and never nests, so a second
    pass produces a different ciphertext (fresh IV and timestamp) over the same
    plaintext under the same key.

    A row that decrypts under neither key is counted and skipped rather than
    aborting the run: one unreadable row must not strand every readable one, and
    the caller is told exactly which rows they were.
    """
    secret = vault_secret(settings)
    previous = tuple(getattr(settings, "sentient_secret_keys_old", ()))
    if not previous:
        raise InvalidRequest(
            "SENTIENT_SECRET_KEY_OLD is not set; there is no previous key to rotate from"
        )

    rotated = 0
    unreadable: list[dict[str, str]] = []
    for row in await state_store.list_all_credentials():
        try:
            token = rotate_token(row["encrypted_key"], secret, previous)
        except Exception:
            # No key material in the report -- only who and which provider.
            unreadable.append({"user_id": str(row["user_id"]), "provider": row["provider"]})
            continue
        await state_store.set_credential_token(str(row["id"]), token)
        rotated += 1

    return {"rotated": rotated, "unreadable": unreadable}
