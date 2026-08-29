import { AlertTriangle, ChevronRight, FileText } from "lucide-react";

import type { RetrievedChunk } from "@/types/threads";

import { loreDisclosure } from "../lore";

/**
 * What grounded one reply, as a disclosure directly above it.
 *
 * It used to sit above the composer and show only the turn in flight, so the
 * provenance of every earlier reply was unrecoverable and a reload lost even
 * that one. Attaching it to the message is what makes it readable turn by turn,
 * and it is why `chat_messages.sources` exists.
 *
 * Which of the four things it says is decided by `loreDisclosure`, not here, so
 * the rule is pinned by tests in a harness with no DOM.
 */
export function SourcesPanel({
  sources,
  retrievalError = null,
  staleIndex = false,
}: {
  sources: RetrievedChunk[] | null;
  retrievalError?: string | null;
  staleIndex?: boolean;
}) {
  const disclosure = loreDisclosure(sources, retrievalError, staleIndex);

  if (disclosure.kind === "failed") {
    return (
      <Disclosure
        icon={<AlertTriangle aria-hidden className="size-3.5 shrink-0 text-warning" />}
        label="Lore lookup failed — answered without lore"
        tone="warning"
      >
        <p className="border-l border-warning/40 pl-3 font-mono text-[11px] break-words text-muted-foreground">
          {disclosure.detail}
        </p>
      </Disclosure>
    );
  }

  if (disclosure.kind === "stale") {
    return (
      <p className="mb-2 flex items-start gap-2 text-[13px] text-warning">
        <AlertTriangle aria-hidden className="mt-0.5 size-3.5 shrink-0" />
        <span>
          This project&rsquo;s documents were indexed with a different embedding model, so none of
          its lore is reachable. Reindex it from project settings.
        </span>
      </p>
    );
  }

  if (disclosure.kind === "none") return null;

  if (disclosure.kind === "empty") {
    // Not a disclosure: there is nothing to disclose. It stays visible because
    // "your question matched none of your lore" is the answer to the question a
    // user asks when a reply looks invented.
    return (
      <p className="mb-2 flex items-center gap-2 text-[13px] text-muted-foreground">
        <FileText aria-hidden className="size-3.5 shrink-0" />
        No lore matched this message
      </p>
    );
  }

  return (
    <Disclosure
      icon={<FileText aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />}
      label={`Read ${disclosure.count} lore ${disclosure.count === 1 ? "passage" : "passages"}`}
    >
      <ul className="space-y-2">
        {(sources ?? []).map((chunk, index) => (
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
            <p className="mt-0.5 whitespace-pre-wrap text-muted-foreground">{chunk.content}</p>
          </li>
        ))}
      </ul>
    </Disclosure>
  );
}

/**
 * A `<details>` rather than a button and a piece of state, so the browser owns
 * the open/closed semantics a screen reader reads and Find-in-page can reach the
 * text inside it. Borderless on purpose: this is a footnote on the reply below
 * it, and a card would make it a peer of the reply.
 */
function Disclosure({
  icon,
  label,
  tone = "muted",
  children,
}: {
  icon: React.ReactNode;
  label: string;
  tone?: "muted" | "warning";
  children: React.ReactNode;
}) {
  return (
    <details className="group mb-2">
      <summary
        className={`flex w-fit cursor-pointer list-none items-center gap-2 rounded text-[13px] focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${
          tone === "warning" ? "text-warning" : "text-muted-foreground"
        } hover:text-foreground`}
      >
        {icon}
        {label}
        <ChevronRight
          aria-hidden
          className="size-3.5 shrink-0 opacity-60 transition-transform duration-[--duration-fast] group-open:rotate-90"
        />
      </summary>
      <div className="mt-2 mb-3">{children}</div>
    </details>
  );
}
