"""User-supplied provider API keys, encrypted at rest.

The domain logic lives in `sentient.services.credentials`; this file is the
HTTP skin over it. Error translation, preserved exactly from the pre-R9 route
bodies:

    InvalidRequest    -> 400 "unknown provider"
    VaultUnavailable  -> 503 "credential vault is not configured" / "... unavailable"
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from sentient.api import deps
from sentient.api.schemas.credentials import CredentialInput
from sentient.core.errors import InvalidRequest, VaultUnavailable
from sentient.services import credentials as service

router = APIRouter()


@router.post("/v1/credentials")
async def create_credential(
    payload: CredentialInput,
    user: tuple[str, str] = Depends(deps.current_user),
):
    user_id, _ = user
    try:
        return await service.store_credential(
            deps.state_store,
            deps.runtime_cache,
            deps._settings,
            user_id=user_id,
            provider=payload.provider,
            api_key=payload.api_key,
        )
    except VaultUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except InvalidRequest as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/v1/credentials")
async def list_credentials(user: tuple[str, str] = Depends(deps.current_user)):
    user_id, _ = user
    try:
        rows = await service.list_credentials(
            deps.state_store, deps._settings, user_id=user_id
        )
    except VaultUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"credentials": rows}


@router.delete("/v1/credentials/{provider}")
async def delete_credential(
    provider: str,
    user: tuple[str, str] = Depends(deps.current_user),
):
    user_id, _ = user
    try:
        deleted = await service.remove_credential(
            deps.state_store,
            deps.runtime_cache,
            deps._settings,
            user_id=user_id,
            provider=provider,
        )
    except VaultUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except InvalidRequest as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"deleted": deleted}
