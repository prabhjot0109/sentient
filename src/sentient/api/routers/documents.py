"""Source documents: upload, list, delete, and per-project ingestion status.

Error translation, preserved exactly from the pre-R9 route bodies:

    InvalidRequest -> 400 "Filename is required" / "Only PDF and TXT files are supported"
    NotFound       -> 404 "File not found" / "project not found"
    QueueFull      -> 503 "ingestion queue is unavailable"
"""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile

from sentient.api import deps
from sentient.core.errors import InvalidRequest, NotFound, QueueFull
from sentient.services import ingestion as service

router = APIRouter()


@router.get("/v1/projects/{project_id}/documents")
async def list_project_documents(
    project_id: str,
    user: tuple[str, str] = Depends(deps.current_user),
):
    """Ingestion status per document — the completion signal for /v1/upload's 202."""
    user_id, _ = user
    if await deps.state_store.get_project(user_id, project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    return {"documents": await deps.state_store.list_documents(project_id)}


@router.post("/v1/upload", status_code=202)
async def upload_file(
    file: UploadFile = File(...),
    api_key: Optional[str] = Form(default=None),
    project_id: Optional[str] = Form(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """Stage an upload and enqueue non-blocking, tenant-scoped ingestion."""
    try:
        credential = x_api_key or api_key
        ctx = await deps.completions_ctx(credential, project_id)
        archives = await deps.get_archives_for_context(ctx)
        safe_name = await service.stage_and_enqueue(
            deps.state_store,
            deps.enqueue_ingest,
            file_obj=file.file,
            filename=file.filename,
            archives=archives,
            ctx=ctx,
            project_id=project_id,
        )
        return {"status": "processing", "filename": safe_name}
    except InvalidRequest as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except QueueFull as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/v1/sources")
async def list_sources(
    project_id: Optional[str] = None,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """List source documents for the caller's archive partition.

    Uploads land in `deps.get_archives_for_context(ctx)` — a per-user/per-project FAISS
    partition — so listing must resolve the same context, or it reports a different
    archive than the one just written to. No key and no project_id resolves to the
    default partition, identical to the pre-R8 behaviour.
    """
    ctx = await deps.completions_ctx(x_api_key, project_id)
    archives = await deps.get_archives_for_context(ctx)
    # stat()s every file in the partition: filesystem I/O, off the event loop.
    sources = await asyncio.to_thread(archives.list_sources)
    return {"sources": sources, "count": len(sources)}


@router.delete("/v1/sources/{filename}")
async def delete_source(
    filename: str,
    project_id: Optional[str] = None,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """Delete a source document from the caller's partition and its registry row.

    Resolving through `deps.completions_ctx` (rather than the api-key-only helper it
    used before) is what makes a project's documents deletable at all; clearing the
    documents row is what stops /v1/projects/{id}/documents reporting a file that is
    no longer on disk.
    """
    ctx = await deps.completions_ctx(x_api_key, project_id)
    archives = await deps.get_archives_for_context(ctx)

    try:
        safe_name, index_metadata = await service.delete_source(
            deps.state_store, archives, filename=filename, project_id=project_id
        )
        return {
            "success": True,
            "message": f"File '{safe_name}' deleted.",
            "index_metadata": index_metadata,
        }
    except NotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except HTTPException:
        # R7's delta records that chat_endpoint's blanket `except Exception -> 500`
        # swallowed its ownership HTTPExceptions and turned every 404 into a 500.
        # This handler has the same shape; do not repeat that bug.
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
