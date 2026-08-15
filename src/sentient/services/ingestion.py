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
from pathlib import Path

from sentient.core.concurrency import IngestJob, ReindexJob


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
