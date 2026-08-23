"""Projects: CRUD, per-project config, the editable persona, and presets.

Error translation, preserved exactly from the pre-R9 route bodies:

    NotFound -> 404 "project not found"

Note the asymmetry with the completions route, which answers 403
"project not found for this key" for the same ownership failure. That is a
real API-design question with a security dimension and R9 deliberately
preserves both; see core/errors.NotOwned.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from sentient.api import deps
from sentient.api.schemas.projects import (
    ConfigInput,
    PersonaInput,
    ProjectInput,
    ProjectRenameInput,
)
from sentient.core.errors import NotFound
from sentient.core.presets import list_presets
from sentient.services import projects as service

router = APIRouter()


@router.post("/v1/projects")
async def create_project(
    payload: ProjectInput,
    user: tuple[str, str] = Depends(deps.current_user),
):
    user_id, _ = user
    return await service.create_project(
        deps.state_store,
        deps._settings,
        user_id=user_id,
        name=payload.name,
        base_preset=payload.base_preset,
    )


@router.get("/v1/projects")
async def list_projects(user: tuple[str, str] = Depends(deps.current_user)):
    user_id, _ = user
    return {"projects": await deps.state_store.list_projects(user_id)}


@router.get("/v1/projects/{project_id}")
async def get_project_endpoint(
    project_id: str,
    user: tuple[str, str] = Depends(deps.current_user),
):
    user_id, _ = user
    try:
        return await service.get_project_detail(
            deps.state_store, user_id=user_id, project_id=project_id
        )
    except NotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/v1/projects/{project_id}")
async def rename_project_endpoint(
    project_id: str,
    payload: ProjectRenameInput,
    user: tuple[str, str] = Depends(deps.current_user),
):
    user_id, _ = user
    try:
        return await service.rename_project(
            deps.state_store, user_id=user_id, project_id=project_id, name=payload.name
        )
    except NotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/v1/projects/{project_id}")
async def delete_project_endpoint(
    project_id: str,
    user: tuple[str, str] = Depends(deps.current_user),
):
    user_id, _ = user
    try:
        await service.delete_project(
            deps.state_store, deps.runtime_cache, user_id=user_id, project_id=project_id
        )
    except NotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"deleted": True}


@router.put("/v1/projects/{project_id}/config")
async def update_config(
    project_id: str,
    payload: ConfigInput,
    user: tuple[str, str] = Depends(deps.current_user),
):
    user_id, _ = user
    try:
        return await service.update_config(
            deps.state_store,
            deps.runtime_cache,
            deps._settings,
            # Passed as a callable, resolved now so a test patching
            # deps.enqueue_reindex is seen (spec 7.1 applies to services too).
            deps.enqueue_reindex,
            user_id=user_id,
            user_key=user[1],
            project_id=project_id,
            fields=payload.model_dump(exclude_unset=True),
        )
    except NotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/v1/projects/{project_id}/persona")
async def set_persona(
    project_id: str,
    payload: PersonaInput,
    user: tuple[str, str] = Depends(deps.current_user),
):
    user_id, _ = user
    try:
        return await service.set_persona(
            deps.state_store,
            deps.runtime_cache,
            user_id=user_id,
            project_id=project_id,
            system_prompt=payload.system_prompt,
        )
    except NotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/v1/presets")
async def presets_endpoint():
    return {"presets": list_presets()}
