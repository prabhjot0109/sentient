/**
 * Mirrors the `documents` table and `GET /v1/projects/{id}/documents`.
 *
 * Unlike `Project` and `ApiKey`, this shape needs NO per-store normalisation.
 * Measured 2026-08-23 against the live Neon branch and a temporary SQLite store:
 * both return the same nine fields. Only two things differ and neither reaches
 * this type -- JSON key order (`size_bytes` last on Postgres, mid-row on SQLite,
 * because migration 0004 added it), and the `id` format (dashed UUID on Postgres,
 * bare 32-char hex on SQLite). Both ids are strings; never parse one.
 */

/** The four values `documents.status` takes. From the DDL comment, confirmed live. */
export type DocumentStatus = "processing" | "ready" | "failed" | "reindexing";

/** Statuses the server will not move off on its own. Polling stops at these. */
export const TERMINAL_STATUSES: readonly DocumentStatus[] = ["ready", "failed"];

export type SourceDocument = {
  /** Postgres: dashed UUID. SQLite: bare hex. A React key, nothing more. */
  id: string;
  project_id: string;
  /**
   * The SANITISED name, from `safe_filename()`. It can differ from the name of
   * the file the user picked, and it -- not the local name -- is the row's
   * identity, together with `project_id`. It is also the path segment
   * `DELETE /v1/sources/{filename}` takes.
   */
  filename: string;
  /** 0 until ingestion finishes; the real chunk count once `status` is "ready". */
  chunk_count: number;
  /** `sha256(provider|model|dimension)[:16]`. Changes when a reindex re-embeds. */
  embedding_signature: string | null;
  status: DocumentStatus;
  /**
   * Written once at staging with the real byte count and preserved across the
   * ready-flip by a COALESCE in both stores' upserts -- the flip carries no byte
   * count, and nulling it there would drop the row out of H6's quota sum.
   */
  size_bytes: number | null;
  /** ISO-8601 with an explicit +00:00 offset on BOTH stores. `Date.parse` is safe. */
  created_at: string;
  updated_at: string;
};
