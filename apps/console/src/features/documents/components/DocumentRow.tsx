import type { SourceDocument } from "@/types/documents";

import { formatBytes, statusLabel } from "../format";

const PILL: Record<SourceDocument["status"], string> = {
  processing: "bg-muted text-muted-foreground",
  ready: "bg-emerald-500/10 text-emerald-600",
  failed: "bg-destructive/10 text-destructive",
  reindexing: "bg-amber-500/10 text-amber-600",
};

export function DocumentRow({
  document,
  onDelete,
}: {
  document: SourceDocument;
  onDelete: (document: SourceDocument) => void;
}) {
  return (
    <li className="flex items-center justify-between gap-4 border-b border-border py-3 last:border-0">
      <div className="min-w-0 space-y-0.5">
        <p className="truncate text-sm font-medium">{document.filename}</p>
        <p className="text-xs text-muted-foreground">
          {formatBytes(document.size_bytes)}
          {/*
            Only on "ready": chunk_count is 0 on a processing row, and
            "0 chunks" next to "Indexing…" reads as a failure that has not happened.
          */}
          {document.status === "ready" && ` · ${document.chunk_count} chunks`}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <span className={`rounded-full px-2 py-0.5 text-xs ${PILL[document.status]}`}>
          {statusLabel(document.status)}
        </span>
        <button
          type="button"
          onClick={() => onDelete(document)}
          className="text-xs text-muted-foreground underline-offset-2 hover:text-destructive hover:underline"
        >
          Delete
        </button>
      </div>
    </li>
  );
}
