import type { RetrievedChunk } from "@/types/threads";

/**
 * What a reply's lore disclosure should say.
 *
 * Four outcomes, because three inputs collapse into two only by losing the
 * distinction that matters. `sources: null` means nothing was recorded, `[]`
 * means retrieval ran and matched nothing, and a `retrievalError` means the
 * lookup itself failed and the reply came from the persona alone. The last two
 * rendered identically until 2026-08-29, which is how a Qdrant cluster refusing
 * every filtered query for want of a payload index reached the user as an NPC
 * that ignored its own lore.
 *
 * A pure function rather than branches inside the component so the rule is
 * testable without a DOM. The console's harness has no jsdom, and the rule is
 * the part worth pinning.
 */
export type LoreDisclosure =
  | { kind: "none" }
  | { kind: "failed"; detail: string }
  | { kind: "stale" }
  | { kind: "empty" }
  | { kind: "chunks"; count: number };

export function loreDisclosure(
  sources: RetrievedChunk[] | null,
  retrievalError: string | null = null,
  staleIndex = false,
): LoreDisclosure {
  // A failure outranks whatever the source list happens to be: a turn that
  // failed to look anything up has no provenance to report, and reporting the
  // stale one would be worse than reporting none.
  if (retrievalError) return { kind: "failed", detail: retrievalError };
  if (sources === null) return { kind: "none" };
  // Ordered before "empty" because it is the same observation with a cause. A
  // project whose documents were embedded under a different signature returns an
  // honest empty list, and calling that "no lore matched" sends the user hunting
  // for a better question when the answer is to reindex.
  if (sources.length === 0 && staleIndex) return { kind: "stale" };
  if (sources.length === 0) return { kind: "empty" };
  return { kind: "chunks", count: sources.length };
}
