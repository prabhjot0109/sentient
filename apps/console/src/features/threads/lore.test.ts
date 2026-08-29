import { describe, expect, it } from "vitest";

import type { RetrievedChunk } from "@/types/threads";

import { loreDisclosure } from "./lore";

const chunk = (source: string): RetrievedChunk => ({
  content: "The Nords of Skyrim resist frost.",
  score: 0.5,
  source,
  page_label: "3",
  chunk_id: 0,
});

describe("loreDisclosure", () => {
  it("says nothing for a message with no recorded provenance", () => {
    expect(loreDisclosure(null)).toEqual({ kind: "none" });
  });

  it("distinguishes a lookup that matched nothing from one that was never made", () => {
    expect(loreDisclosure([])).toEqual({ kind: "empty" });
  });

  it("counts the passages a reply was grounded in", () => {
    expect(loreDisclosure([chunk("a.pdf"), chunk("b.pdf")])).toEqual({ kind: "chunks", count: 2 });
  });

  it("reports a failed lookup rather than an empty result", () => {
    // The exact case that shipped silently: Qdrant refuses a filter on a payload
    // field it has no index for, the service downgrades to an ungrounded answer,
    // and `sources` is [] for a reason that has nothing to do with the lore.
    const detail =
      "InactiveRpcError: Index required but not found for metadata.embedding_signature";
    expect(loreDisclosure([], detail)).toEqual({ kind: "failed", detail });
  });

  it("names a stale index rather than blaming the question", () => {
    // Measured 2026-08-29: a project whose documents carried signature
    // 71d147258a02c83c while the runtime queried 8df2da26ff37503b returned an
    // honest empty list on every question. "No lore matched" sent the user
    // hunting for better wording when the fix was a reindex.
    expect(loreDisclosure([], null, true)).toEqual({ kind: "stale" });
  });

  it("stays quiet about staleness while chunks still come back", () => {
    expect(loreDisclosure([chunk("a.pdf")], null, true)).toEqual({ kind: "chunks", count: 1 });
  });

  it("lets a failure outrank a stale source list", () => {
    expect(loreDisclosure([chunk("a.pdf")], "boom")).toEqual({ kind: "failed", detail: "boom" });
  });
});
