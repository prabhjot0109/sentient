import { Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Menu } from "@/components/ui/Menu";
import type { SourceDocument } from "@/types/documents";

import { formatBytes, statusLabel } from "../format";

/**
 * Tone per status, on the shared `Badge` rather than four hand-written class
 * strings. The colours are unchanged -- they are the measured `--success`,
 * `--warning` and `--destructive` tints -- but the shape is now the same one the
 * key list and the project header use.
 */
const TONE = {
  processing: "neutral",
  ready: "success",
  failed: "danger",
  reindexing: "warning",
} as const;

export function DocumentRow({
  document,
  onDelete,
}: {
  document: SourceDocument;
  onDelete: (document: SourceDocument) => void;
}) {
  const working = document.status === "processing" || document.status === "reindexing";

  return (
    <li className="flex items-center gap-3 border-b border-border py-3 last:border-0">
      <div className="min-w-0 flex-1 space-y-0.5">
        <p className="truncate text-sm font-medium" title={document.filename}>
          {document.filename}
        </p>
        <p className="text-xs text-muted-foreground">
          {formatBytes(document.size_bytes)}
          {/*
            Only on "ready": chunk_count is 0 on a processing row, and
            "0 chunks" next to "Indexing…" reads as a failure that has not happened.
          */}
          {document.status === "ready" && ` · ${document.chunk_count} chunks`}
        </p>
        {/*
          A failed row says what to DO, because it cannot say what went wrong.
          Verified against the live Neon branch on 2026-08-29: `documents` has
          exactly nine columns and none of them is a reason -- ingestion fails
          asynchronously, long after the 202, and the message goes to the server
          log and nowhere else. Rendering a `document.error` here would have been
          a field that does not exist. Giving the user the one action that is
          actually available beats a red pill with nothing beside it.
        */}
        {document.status === "failed" && (
          <p className="text-xs text-destructive">
            Indexing failed. Delete this file and upload it again; if it fails twice, the server log
            has the reason.
          </p>
        )}
      </div>

      <Badge tone={TONE[document.status]}>
        {working && (
          <span
            aria-hidden
            className="size-1.5 rounded-full bg-current motion-safe:animate-pulse"
          />
        )}
        {statusLabel(document.status)}
      </Badge>

      <Menu
        label={`Actions for ${document.filename}`}
        items={[
          {
            label: "Delete",
            icon: Trash2,
            danger: true,
            onSelect: () => onDelete(document),
          },
        ]}
      />
    </li>
  );
}
