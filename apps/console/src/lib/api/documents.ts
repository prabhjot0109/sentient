import type { SourceDocument } from "@/types/documents";

import { apiFetch } from "./client";

/**
 * Unwrapped at the boundary, exactly as `projects.ts` unwraps `{projects:[…]}`.
 * Every consumer wants the array.
 */
export const listDocuments = (projectId: string) =>
  apiFetch<{ documents: SourceDocument[] }>(`/v1/projects/${projectId}/documents`).then(
    (r) => r.documents,
  );

/**
 * `POST /v1/upload` is multipart and answers 202 with no document id -- the row's
 * identity is (project_id, filename). The returned `filename` is the SANITISED
 * name; callers must key optimistic state on it, never on `file.name`.
 *
 * NOTE the deliberate absence of a `content-type` header. The browser has to set
 * `multipart/form-data` itself so it can append the boundary; setting it by hand
 * produces a body FastAPI cannot parse. `client.ts` only ever adds
 * `authorization`, so passing FormData straight through works.
 *
 * `project_id` is a FORM FIELD and it is optional on the backend. Omitting it
 * still returns 202, but writes to the caller's default partition and creates NO
 * documents row -- the upload would appear to vanish. Always send it.
 */
export const uploadDocument = (projectId: string, file: File) => {
  const body = new FormData();
  body.append("file", file);
  body.append("project_id", projectId);
  return apiFetch<{ status: string; filename: string }>("/v1/upload", { method: "POST", body });
};

/**
 * Keyed by FILENAME, not id -- hence the encodeURIComponent, without which a name
 * containing a space, `#` or `?` 404s or hits a different route.
 *
 * This 404s on the FILE, not the row: `delete_source` checks the path exists and
 * raises before it touches the documents table. A row whose file is gone from disk
 * cannot be deleted here, and the honest response is to show the error rather than
 * to drop the row from the cache and let a reload contradict you.
 */
export const deleteDocument = (projectId: string, filename: string) =>
  apiFetch<{ success: boolean; message: string }>(
    `/v1/sources/${encodeURIComponent(filename)}?project_id=${projectId}`,
    { method: "DELETE" },
  );
