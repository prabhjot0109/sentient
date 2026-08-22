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
import codecs
import os
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath

from sentient.core.concurrency import IngestJob, ReindexJob
from sentient.core.errors import InvalidRequest, NotFound, QueueFull
from sentient.services.runtime import embedding_signature

_ALLOWED_SUFFIXES = (".pdf", ".txt")
_PDF_MAGIC = b"%PDF-"
# One mebibyte per read. Large enough that a 25 MB upload is 25 reads, small
# enough that an oversized one is stopped long before it fills the disk.
_CHUNK_BYTES = 1024 * 1024
# The window sniffed for magic bytes. Every signature we check lives in the
# first few bytes; the rest is slack so a truncated UTF-8 character at the
# boundary is a rounding error rather than a false rejection.
_SNIFF_BYTES = 1024


def bare_filename(raw: str | None) -> str:
    """Strip every directory component a client may have sent, on either OS.

    `os.path.basename` alone is not enough: on POSIX it treats a backslash as an
    ordinary character, so `..\\..\\evil.txt` passed through untouched. Both
    separators are stripped here regardless of the host OS, because the server
    runs on both, and a name that reaches the filesystem must not be able to
    address anything outside the tenant's own partition.
    """
    if not raw:
        raise InvalidRequest("Filename is required")
    if "\x00" in raw:
        raise InvalidRequest("Filename contains a null byte")

    name = PurePosixPath(PureWindowsPath(raw).name).name.strip()
    if not name or name in {".", ".."}:
        raise InvalidRequest("Filename is required")
    return name


def safe_filename(raw: str | None) -> str:
    """A bare filename that also carries a supported extension."""
    name = bare_filename(raw)
    if not name.lower().endswith(_ALLOWED_SUFFIXES):
        raise InvalidRequest("Only PDF and TXT files are supported")
    return name


def sniff_content_type(head: bytes, suffix: str) -> str:
    """Confirm the bytes agree with the extension. The extension is a claim."""
    lowered = suffix.lower()
    if lowered == ".pdf":
        if not head.startswith(_PDF_MAGIC):
            raise InvalidRequest("File does not look like a PDF")
        return "application/pdf"

    if lowered == ".txt":
        if head.startswith(_PDF_MAGIC) or b"\x00" in head:
            raise InvalidRequest("File does not look like plain text")
        try:
            # Incremental, with final=False: the head is a fixed-size window that
            # routinely lands mid-character in any non-ASCII file, and a truncated
            # trailing sequence is not evidence of binary. This decoder tolerates
            # exactly that while still rejecting invalid bytes. Trimming a fixed
            # number of tail bytes instead does not work — the trim can land
            # mid-sequence too.
            codecs.getincrementaldecoder("utf-8")().decode(head, final=False)
        except UnicodeDecodeError:
            raise InvalidRequest("File does not look like plain text") from None
        return "text/plain"

    raise InvalidRequest("Only PDF and TXT files are supported")


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
            await state_store.set_document_status(job.project_id, job.filename, "failed")
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
    settings,
) -> str:
    """Validate, stage to a temp file, register the row, and enqueue the job.

    Returns the safe filename. This is the operation `upload_file` used to
    perform inline, which is why only its own route could invoke it (spec
    section 2, defect 2).

    Validation lives here rather than in the route for the same reason: every
    caller gets the size cap, the magic-byte check and the quota, including
    callers that do not exist yet.

    **Cleanup is owned here, not by the caller.** Pre-R9 the route cleaned the
    staged file on two separate `except` branches; folding that into this
    function means every failure after staging removes the temp file, including
    failures a future caller has not thought of. On success the file is left
    alone deliberately -- `run_ingest_job` moves it into the archive.
    """
    safe_name = safe_filename(filename)
    suffix = Path(safe_name).suffix
    max_bytes = settings.upload_max_bytes
    staging_dir = archives.data_dir / ".ingest"

    def _stage_upload() -> tuple[str, int]:
        staging_dir.mkdir(parents=True, exist_ok=True)
        fd, path = tempfile.mkstemp(prefix="upload-", suffix=suffix, dir=staging_dir)
        written = 0
        sniffed = False
        try:
            with os.fdopen(fd, "wb") as buffer:
                while chunk := file_obj.read(_CHUNK_BYTES):
                    if not sniffed:
                        sniff_content_type(chunk[:_SNIFF_BYTES], suffix)
                        sniffed = True
                    if written + len(chunk) > max_bytes:
                        # Rejected before the bytes land. Content-Length is a
                        # client's claim, so a caller that lies about it must not
                        # be able to fill the disk before anyone notices.
                        raise InvalidRequest(
                            f"File exceeds the {max_bytes // (1024 * 1024)} MB upload limit"
                        )
                    buffer.write(chunk)
                    written += len(chunk)
        except BaseException:
            Path(path).unlink(missing_ok=True)
            raise
        if not written:
            Path(path).unlink(missing_ok=True)
            raise InvalidRequest("File is empty")
        return path, written

    staged_path, size_bytes = await asyncio.to_thread(_stage_upload)
    try:
        if ctx.user_id is not None:
            used = await state_store.user_storage_bytes(ctx.user_id)
            if used + size_bytes > settings.upload_user_quota_bytes:
                raise InvalidRequest(
                    "Storage quota exceeded: "
                    f"{(used + size_bytes) // (1024 * 1024)} MB requested, "
                    f"{settings.upload_user_quota_bytes // (1024 * 1024)} MB allowed"
                )

        signature = ""
        if project_id is not None:
            signature = embedding_signature(ctx.rag_settings)
            await state_store.register_document(
                project_id, safe_name, 0, signature, status="processing", size_bytes=size_bytes
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
    """Remove a source file from the partition, the index, and the registry.

    `bare_filename`, not `safe_filename`: this must delete rows that predate the
    extension allow-list, and answering 400 for a name that simply is not there
    would change a public error string. The traversal strip is the part that
    matters here, because this call reaches `os.remove`.
    """
    safe_name = bare_filename(filename)
    file_path = archives.data_dir / safe_name

    if not await asyncio.to_thread(file_path.exists):
        raise NotFound("File not found")

    await asyncio.to_thread(os.remove, file_path)
    index_metadata = await archives.remove_file(safe_name)
    if project_id is not None:
        await state_store.delete_document(project_id, safe_name)
    return safe_name, index_metadata
