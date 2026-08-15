"""Document ingestion and project reindexing — the work, not the plumbing.

The `IngestQueue` instances live in `api/deps.py` because they are process-local
infrastructure that the app lifespan starts and stops. What they *do* lives
here, as plain coroutines taking `state_store` and an already-resolved
`archives` client as explicit arguments.

That split is the point of the layer rule: `services/` may not import
`api/deps.py`, so anything the api layer owns has to arrive as a parameter.
The payoff is that a reindex can be driven from a CLI, a test, or a future
out-of-process worker without a route handler in the picture.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from pathlib import Path

from sentient.core.concurrency import IngestJob, ReindexJob
from sentient.core.errors import InvalidRequest, NotFound, QueueFull
from sentient.services.runtime import embedding_signature


async def run_ingest_job(job: IngestJob, *, state_store, archives) -> None:
    """Move a staged upload into the archive and index it.

    The `finally` clause is load-bearing: the staged temp file is removed on
    every path, including the failure path, or a rejected upload leaks disk.
    """
    staged_path = Path(job.file_path)
    final_path = archives.data_dir / job.filename
    try:
        if staged_path != final_path:
            await asyncio.to_thread(final_path.parent.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(os.replace, staged_path, final_path)

        metadata = await archives.add_file(
            str(final_path),
            user_key=job.user_key,
            project_id=job.project_id,
            embedding_signature=job.embedding_signature,
        )
        if job.project_id is not None:
            await state_store.register_document(
                job.project_id,
                job.filename,
                (metadata or {}).get("added_chunk_count", 0),
                job.embedding_signature,
                status="ready",
            )
    except Exception:
        if job.project_id is not None:
            await state_store.set_document_status(
                job.project_id, job.filename, "failed"
            )
        raise
    finally:
        if staged_path != final_path and staged_path.exists():
            await asyncio.to_thread(staged_path.unlink)


async def run_reindex_job(job: ReindexJob, *, state_store, archives) -> None:
    """Purge the project's vectors and rebuild them under a new embedding signature.

    On any failure the project is put back into `reindexing_required` so the
    guard keeps returning 409 rather than serving results from a half-rebuilt
    index.
    """
    documents = await state_store.list_documents(job.project_id)
    try:
        await asyncio.to_thread(archives.clear_project, job.user_key, job.project_id)
        if archives.settings.vector_backend == "faiss":
            await asyncio.to_thread(archives.reset_index)

        for document in documents:
            await state_store.set_document_status(
                job.project_id, document["filename"], "reindexing"
            )
            metadata = await archives.add_file(
                str(archives.data_dir / document["filename"]),
                user_key=job.user_key,
                project_id=job.project_id,
                embedding_signature=job.embedding_signature,
            )
            await state_store.register_document(
                job.project_id,
                document["filename"],
                (metadata or {}).get("added_chunk_count", 0),
                job.embedding_signature,
                status="ready",
            )
        await state_store.set_project_status(job.project_id, "active")
    except Exception:
        await state_store.set_project_status(job.project_id, "reindexing_required")
        raise


async def stage_and_enqueue(
    state_store,
    enqueue,
    *,
    file_obj,
    filename: str | None,
    archives,
    ctx,
    project_id: str | None,
) -> str:
    """Validate, stage to a temp file, register the row, and enqueue the job.

    Returns the safe filename. This is the operation `upload_file` used to
    perform inline, which is why only its own route could invoke it (spec
    section 2, defect 2).

    **Cleanup is owned here, not by the caller.** Pre-R9 the route cleaned the
    staged file on two separate `except` branches; folding that into this
    function means every failure after staging removes the temp file, including
    failures a future caller has not thought of. On success the file is left
    alone deliberately -- `run_ingest_job` moves it into the archive.
    """
    if not filename:
        raise InvalidRequest("Filename is required")

    safe_name = os.path.basename(filename)
    if not safe_name.lower().endswith((".pdf", ".txt")):
        raise InvalidRequest("Only PDF and TXT files are supported")

    staging_dir = archives.data_dir / ".ingest"

    def _stage_upload() -> str:
        staging_dir.mkdir(parents=True, exist_ok=True)
        fd, path = tempfile.mkstemp(
            prefix="upload-", suffix=Path(safe_name).suffix, dir=staging_dir
        )
        with os.fdopen(fd, "wb") as buffer:
            shutil.copyfileobj(file_obj, buffer)
        return path

    staged_path = await asyncio.to_thread(_stage_upload)
    try:
        signature = ""
        if project_id is not None:
            signature = embedding_signature(ctx.rag_settings)
            await state_store.register_document(
                project_id, safe_name, 0, signature, status="processing"
            )

        job = IngestJob(
            project_id=project_id,
            user_key=ctx.user_key,
            api_key=ctx.llm_settings["api_key"],
            file_path=staged_path,
            filename=safe_name,
            embedding_signature=signature,
            archives=archives,
        )
        try:
            await enqueue(job)
        except (asyncio.QueueFull, RuntimeError) as exc:
            if project_id is not None:
                await state_store.set_document_status(project_id, safe_name, "failed")
            raise QueueFull("ingestion queue is unavailable") from exc
    except Exception:
        if os.path.exists(staged_path):
            await asyncio.to_thread(os.remove, staged_path)
        raise

    return safe_name


async def delete_source(state_store, archives, *, filename: str, project_id: str | None):
    """Remove a source file from the partition, the index, and the registry."""
    safe_name = os.path.basename(filename)
    file_path = archives.data_dir / safe_name

    if not await asyncio.to_thread(file_path.exists):
        raise NotFound("File not found")

    await asyncio.to_thread(os.remove, file_path)
    index_metadata = await archives.remove_file(safe_name)
    if project_id is not None:
        await state_store.delete_document(project_id, safe_name)
    return safe_name, index_metadata
