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

from sentient.adapters.state.schema import _CONFIG_COLUMNS
from sentient.core.concurrency import ReindexJob
from sentient.core.errors import NotFound
from sentient.core.presets import get_preset
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


# Everything the settings pane can write, read back. persona_prompt is reported
# separately because it resolves through the preset fallback and the others do not.
# Derived rather than listed: a hand-maintained copy drifts the moment a knob is
# added, and the symptom is a pane that silently cannot see it.
_READABLE_CONFIG_FIELDS = tuple(c for c in _CONFIG_COLUMNS if c != "persona_prompt")


async def get_project_detail(state_store, *, user_id: str, project_id: str) -> dict[str, Any]:
    """The project, its stored config, and the persona the NPC actually speaks with.

    Every config field is reported **as stored**: `null` means "unset", not "the
    default happens to be this". F3 has to tell those apart, because rendering a
    resolved default into an input and saving it pins a value the user never chose.

    The persona is the opposite case and reported **as resolved**. H1's Finding 4
    measured a project whose `persona_prompt` was NULL while the NPC visibly had a
    persona from its preset, so an editor reading the stored value would render a
    blank field over a live persona and overwrite it on the first save.
    `persona_source` is what lets the pane show which of the two it is looking at.
    """
    project = await state_store.get_project(user_id, project_id)
    if project is None:
        raise NotFound("project not found")

    stored = await state_store.get_project_config(project_id) or {}
    persona = stored.get("persona_prompt")
    if persona:
        persona_source = "custom"
    else:
        persona = get_preset(project.get("base_preset") or "")
        persona_source = "preset" if persona else "generic"

    return {
        **project,
        "config": {field: stored.get(field) for field in _READABLE_CONFIG_FIELDS},
        "persona_prompt": persona,
        "persona_source": persona_source,
    }


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
    config = await state_store.upsert_project_config(project_id, persona_prompt=system_prompt)
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
    prior = (await state_store.get_project_config(project_id) or {}).get("embedding_signature")
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
    if prior is not None and prior != new_signature and project["status"] != "reindexing_required":
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
