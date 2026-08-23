import type { RetrievedChunk } from "@/types/threads";

/** The chunks the `sentient.chat.meta` frame carried — what grounded this turn. */
export function SourcesPanel({ sources }: { sources: RetrievedChunk[] }) {
  if (sources.length === 0) return null;
  return (
    <details className="rounded-md border border-border p-3">
      <summary className="cursor-pointer text-sm font-medium">
        Grounded in {sources.length} chunk{sources.length === 1 ? "" : "s"}
      </summary>
      <ul className="mt-2 space-y-2">
        {sources.map((chunk, index) => (
          <li key={`${chunk.source}-${chunk.chunk_id ?? index}`} className="text-xs">
            <p className="font-medium">
              {chunk.source}
              {chunk.page_label && ` · p.${chunk.page_label}`}
              {chunk.score !== null && ` · ${chunk.score.toFixed(3)}`}
            </p>
            <p className="mt-0.5 line-clamp-3 text-muted-foreground">{chunk.content}</p>
          </li>
        ))}
      </ul>
    </details>
  );
}
