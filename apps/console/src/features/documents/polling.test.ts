import { describe, expect, it } from "vitest";

import type { SourceDocument } from "@/types/documents";

import { pollIntervalMs, shouldPoll } from "./polling";

const doc = (status: SourceDocument["status"]): SourceDocument => ({
  id: "d1",
  project_id: "p1",
  filename: "lore.txt",
  chunk_count: 0,
  embedding_signature: "sig",
  status,
  size_bytes: 177,
  created_at: "2026-08-23T11:13:51.657789+00:00",
  updated_at: "2026-08-23T11:13:51.657789+00:00",
});

describe("shouldPoll", () => {
  it("does not poll before the first response", () => {
    expect(shouldPoll(undefined)).toBe(false);
  });

  it("does not poll an empty project", () => {
    expect(shouldPoll([])).toBe(false);
  });

  it("polls while a document is processing", () => {
    expect(shouldPoll([doc("processing")])).toBe(true);
  });

  it("polls while a document is reindexing", () => {
    expect(shouldPoll([doc("reindexing")])).toBe(true);
  });

  it("stops once every document is terminal", () => {
    expect(shouldPoll([doc("ready"), doc("failed")])).toBe(false);
  });

  it("keeps polling if even one row is unsettled", () => {
    expect(shouldPoll([doc("ready"), doc("processing")])).toBe(true);
  });
});

describe("pollIntervalMs", () => {
  it("polls fast while the answer is probably imminent", () => {
    expect(pollIntervalMs(0)).toBe(1500);
    expect(pollIntervalMs(19)).toBe(1500);
  });

  it("backs off once 30s of fast polling has not settled it", () => {
    expect(pollIntervalMs(20)).toBe(5000);
    expect(pollIntervalMs(43)).toBe(5000);
  });

  it("falls back to a slow heartbeat rather than stopping", () => {
    expect(pollIntervalMs(44)).toBe(15000);
    expect(pollIntervalMs(10_000)).toBe(15000);
  });
});
