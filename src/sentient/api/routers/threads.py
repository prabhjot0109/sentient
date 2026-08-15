"""Project-scoped chat threads and their messages.

This is R7's chat-history system and the only one — B0 deleted the legacy
`chat_sessions` surface. No service layer: each handler is an ownership check
plus a state-store call (spec D6).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from sentient.api import deps

router = APIRouter()


@router.get("/v1/projects/{project_id}/threads")
async def list_project_threads(
    project_id: str,
    user: tuple[str, str] = Depends(deps.current_user),
):
    user_id, _ = user
    if await deps.state_store.get_project(user_id, project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    return {"threads": await deps.state_store.list_threads(project_id)}


@router.delete("/v1/threads/{thread_id}")
async def delete_thread_endpoint(
    thread_id: str,
    user: tuple[str, str] = Depends(deps.current_user),
):
    user_id, _ = user
    if not await deps.state_store.delete_thread(user_id, thread_id):
        raise HTTPException(status_code=404, detail="thread not found")
    return {"deleted": True}


@router.get("/v1/threads/{thread_id}/messages")
async def list_thread_messages(
    thread_id: str,
    limit: int = 50,
    user: tuple[str, str] = Depends(deps.current_user),
):
    if not 1 <= limit <= 200:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 200")
    user_id, _ = user
    if await deps.state_store.get_thread(user_id, thread_id) is None:
        raise HTTPException(status_code=404, detail="thread not found")
    return {"messages": await deps.state_store.list_messages(thread_id, limit=limit)}
