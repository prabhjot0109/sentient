import type { DocumentStatus } from "@/types/documents";

/**
 * `size_bytes` is nullable on both stores -- rows written before migration 0004
 * have no size, and a null there is "unknown", not zero. Zero is a real value the
 * upload path cannot produce (an empty file 400s), so the two must not collapse.
 */
export const formatBytes = (bytes: number | null): string => {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

/** The four `documents.status` values, in the user's vocabulary rather than the table's. */
export const statusLabel = (status: DocumentStatus): string =>
  ({
    processing: "Indexing…",
    ready: "Ready",
    failed: "Failed",
    reindexing: "Re-embedding…",
  })[status];
