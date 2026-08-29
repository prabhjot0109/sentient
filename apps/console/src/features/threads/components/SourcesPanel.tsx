import { ChevronRight } from "lucide-react";

import type { RetrievedChunk } from "@/types/threads";

/** The chunks the `sentient.chat.meta` frame carried — what grounded this turn. */
export function SourcesPanel({ sources }: { sources: RetrievedChunk[] }) {
  if (sources.length === 0) return null;
  return (
    <details className="group rounded-lg border border-border bg-card p-3">
      <summary className="flex cursor-pointer list-none items-center gap-2 rounded text-sm font-medium focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
        <ChevronRight
          aria-hidden
          className="size-3.5 shrink-0 text-muted-foreground transition-transform duration-[--duration-fast] group-open:rotate-90"
        />
        Grounded in {sources.length} chunk{sources.length === 1 ? "" : "s"}
        {/*
          The provenance of the answer above it, and the one thing on this
          surface that proves retrieval ran at all. It stays collapsed by default
          because it is evidence, not content.
        */}
      </summary>
      <ul className="mt-2 space-y-2">
        {sources.map((chunk, index) => (
          <li
            key={`${chunk.source}-${chunk.chunk_id ?? index}`}
            className="border-l border-border pl-3 text-xs"
          >
            <p className="font-mono text-[11px] text-muted-foreground">
              {chunk.source}
              {chunk.page_label && ` · p.${chunk.page_label}`}
              {/*
                `score` is nullable and the null is real -- it means the backend
                reported none, not that the chunk scored zero. It also means
                different things per backend: a cosine floor on FAISS, a
                rank-fusion artefact on Qdrant. Printed, never interpreted.
              */}
              {chunk.score !== null && ` · ${chunk.score.toFixed(3)}`}
            </p>
            <p className="mt-0.5 line-clamp-3 text-muted-foreground">{chunk.content}</p>
          </li>
        ))}
      </ul>
    </details>
  );
}
