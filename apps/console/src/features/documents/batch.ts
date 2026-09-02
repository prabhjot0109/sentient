/**
 * Uploading several files is N requests, not one.
 *
 * `POST /v1/upload` takes exactly one file, and that is worth preserving rather
 * than working around. Per request the backend enforces a streaming byte cap, a
 * magic-byte sniff, the per-user storage quota and the rate limit, and it writes
 * one `documents` row whose status is that file's own. A batch endpoint would
 * have to reinvent every one of those and answer a question this shape never
 * asks: what does a 202 mean when the third of five files was rejected?
 *
 * Sequential rather than parallel. The gain from parallelism is small because
 * ingestion is queued behind a single FIFO worker anyway, and the costs are real:
 * a burst trips RATE_LIMIT_UPLOADS_PER_HOUR, and the arrival order stops matching
 * the order the user picked.
 */

/** What actually happened, including the case where only some of it worked. */
export type BatchUploadResult = {
  /** Server-sanitised filenames, which may differ from what the user picked. */
  uploaded: string[];
  failed: { name: string; error: unknown }[];
};

/**
 * Upload every file, and do not let one failure discard the rest.
 *
 * Throws only when NOTHING succeeded, and then it throws the first error rather
 * than a summary. That keeps the single-file path byte-identical to what it was
 * before batching existed: one file that fails still surfaces its own typed error
 * to `ErrorState`, with the backend's own sentence intact.
 *
 * A partial success returns instead, because the successes are real and already
 * indexing. Reporting them as an error would tell the user to retry files that
 * are on the server, and re-uploading is not free.
 */
export async function uploadAll(
  files: File[],
  upload: (file: File) => Promise<{ filename: string }>,
): Promise<BatchUploadResult> {
  const result: BatchUploadResult = { uploaded: [], failed: [] };

  for (const file of files) {
    try {
      const response = await upload(file);
      result.uploaded.push(response.filename);
    } catch (error) {
      result.failed.push({ name: file.name, error });
    }
  }

  if (result.uploaded.length === 0 && result.failed.length > 0) {
    throw result.failed[0].error;
  }
  return result;
}

/** The line a person reads after dropping several files at once. */
export function describeBatch(result: BatchUploadResult): { title: string; body: string } {
  const { uploaded, failed } = result;

  if (failed.length === 0) {
    return {
      title:
        uploaded.length === 1 ? `Uploading ${uploaded[0]}` : `Uploading ${uploaded.length} files`,
      body: "They appear below and turn Ready once indexing finishes.",
    };
  }

  // Named, not counted. "2 files failed" sends the user back to the file picker
  // to work out which two.
  const names = failed.map((f) => f.name).join(", ");
  return {
    title: `Uploaded ${uploaded.length} of ${uploaded.length + failed.length}`,
    body: `Could not upload ${names}. Check the file type and size, then try those again.`,
  };
}
