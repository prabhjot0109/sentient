"""Project lifecycle and configuration, including the reindex guard.

The interesting operation here is `update_config`. Changing an embedding
setting invalidates every vector already stored for the project: the old
vectors live in a different embedding space, so retrieval against them is
silently wrong rather than merely stale. So a signature change flips the
project to `reindexing_required` and enqueues a rebuild, and the retrieval
paths answer 409 until it finishes.

`enqueue_reindex` arrives as a callable rather than an import: the queue is
process-local infrastructure owned by the api layer, and `services/` may not
import it.
"""

from __future__ import annotations

from typing import Any

from sentient.core.concurrency import ReindexJob
from sentient.core.errors import NotFound
from sentient.services.runtime import embedding_signature, resolve_runtime_context


async def create_project(
    state_store,
    settings,
    *,
    user_id: str,
    name: str,
    base_preset: str,
) -> dict[str, Any]:
    """Create the project, then stamp the embedding signature it resolves to."""
    project = await state_store.create_project(user_id, name, base_preset)
    ctx = await resolve_runtime_context(
        state_store,
        settings,
        user_id=user_id,
        user_key="_",
        project_id=project["id"],
    )
    await state_store.upsert_project_config(
        project["id"], embedding_signature=embedding_signature(ctx.rag_settings)
    )
    return project


async def rename_project(state_store, *, user_id: str, project_id: str, name: str):
    project = await state_store.rename_project(user_id, project_id, name)
    if project is None:
        raise NotFound("project not found")
    return project


async def delete_project(state_store, runtime_cache, *, user_id: str, project_id: str) -> bool:
    """Delete a project and everything under it (config, threads, messages, documents).

    Vectors are NOT removed here — orphaned partitions are unreachable because every
    query filters on user_key+project_id, so this is disk cost, not a leak. Reclaiming
    it is tracked in the post-R8 TODO under "Storage reclamation".
    """
    if not await state_store.delete_project(user_id, project_id):
        raise NotFound("project not found")
    # Without this, cached contexts keep serving turns for a deleted project until
    # the RuntimeCache TTL expires.
    runtime_cache.invalidate(project_id)
    return True


async def set_persona(
    state_store,
    runtime_cache,
    *,
    user_id: str,
    project_id: str,
    system_prompt: str,
) -> dict[str, Any]:
    if await state_store.get_project(user_id, project_id) is None:
        raise NotFound("project not found")
    config = await state_store.upsert_project_config(
        project_id, persona_prompt=system_prompt
    )
    runtime_cache.invalidate(project_id)
    return config


async def update_config(
    state_store,
    runtime_cache,
    settings,
    enqueue_reindex,
    *,
    user_id: str,
    user_key: str,
    project_id: str,
    fields: dict[str, Any],
) -> dict[str, Any]:
    project = await state_store.get_project(user_id, project_id)
    if project is None:
        raise NotFound("project not found")
    prior = (await state_store.get_project_config(project_id) or {}).get(
        "embedding_signature"
    )
    await state_store.upsert_project_config(project_id, **fields)
    ctx = await resolve_runtime_context(
        state_store,
        settings,
        user_id=user_id,
        user_key="_",
        project_id=project_id,
    )
    config = await state_store.upsert_project_config(
        project_id, embedding_signature=embedding_signature(ctx.rag_settings)
    )
    new_signature = config["embedding_signature"]
    runtime_cache.invalidate(project_id)
    if (
        prior is not None
        and prior != new_signature
        and project["status"] != "reindexing_required"
    ):
        await state_store.set_project_status(project_id, "reindexing_required")
        await enqueue_reindex(
            ReindexJob(
                project_id=project_id,
                user_key=user_key,
                api_key=None,
                embedding_signature=new_signature,
                user_id=user_id,
            )
        )
    return config
