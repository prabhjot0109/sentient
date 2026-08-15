"""Product API keys (`sk-sent-…`) — issue, list, revoke.

No service layer: every handler is a one-line passthrough to the state store,
and wrapping those would add a file to open for no benefit (spec D6).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from sentient.adapters.auth import generate_api_key
from sentient.api import deps
from sentient.api.schemas.keys import KeyInput

router = APIRouter()


@router.post("/v1/keys")
async def create_key(
    payload: KeyInput,
    user: tuple[str, str] = Depends(deps.current_user),
):
    user_id, _ = user
    raw_key, key_hash = generate_api_key()
    row = await deps.state_store.create_api_key(user_id, key_hash, label=payload.label)
    return {"id": row["id"], "api_key": raw_key, "label": payload.label}


@router.get("/v1/keys")
async def list_keys(user: tuple[str, str] = Depends(deps.current_user)):
    user_id, _ = user
    return {"keys": await deps.state_store.list_api_keys(user_id)}


@router.delete("/v1/keys/{key_id}")
async def delete_key(
    key_id: str,
    user: tuple[str, str] = Depends(deps.current_user),
):
    user_id, _ = user
    revoked = await deps.state_store.revoke_api_key(user_id, key_id)
    if revoked:
        deps.identity_cache.clear()
    return {"revoked": revoked}
