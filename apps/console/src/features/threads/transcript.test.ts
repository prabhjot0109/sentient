import { describe, expect, it } from "vitest";

import type { ChatMessage } from "@/types/threads";

import { awaitingWrite, draftLanded, showDraft, transcriptPollMs } from "./transcript";

const message = (role: ChatMessage["role"], content: string): ChatMessage => ({
  id: `m-${role}-${content}`,
  thread_id: "t1",
  role,
  content,
  created_at: "2026-08-23T17:28:28.293144+00:00",
  model: role === "assistant" ? "openai/gpt-oss-20b" : null,
  prompt_tokens: null,
  completion_tokens: null,
  total_tokens: null,
});

const REPLY = "I am a humble Nord of the north.";
const SETTLED = [message("user", "Who are you?"), message("assistant", REPLY)];

describe("draftLanded", () => {
  it("is false before the first response", () => {
    expect(draftLanded(undefined, REPLY)).toBe(false);
  });

  it("is false against an empty transcript", () => {
    expect(draftLanded([], REPLY)).toBe(false);
  });

  it("is true once the identical assistant row is there", () => {
    // Exact equality is sound because the server persists "".join(parts) built
    // from the same strings it streamed as delta.content.
    expect(draftLanded(SETTLED, REPLY)).toBe(true);
  });

  it("does not match the user's own message", () => {
    expect(draftLanded([message("user", REPLY)], REPLY)).toBe(false);
  });

  it("does not match a DIFFERENT assistant message on the same thread", () => {
    // The across-turns case. Turn 2's reply has not landed just because turn 1's
    // is sitting at the end of the transcript.
    expect(draftLanded(SETTLED, "A second, later reply.")).toBe(false);
  });

  it("is false for an empty draft, which no row can ever match", () => {
    expect(draftLanded(SETTLED, "")).toBe(false);
  });
});

describe("awaitingWrite", () => {
  it("does not ask during the stream itself", () => {
    // A stream is a push. The transcript cannot change while it runs.
    expect(awaitingWrite([], REPLY, true)).toBe(false);
  });

  it("asks while the deferred write is outstanding", () => {
    // Measured 2026-08-23: at 406ms after [DONE] the transcript read ZERO
    // messages, and the assistant row landed 1.3-1.7s after the stream closed.
    expect(awaitingWrite([], REPLY, false)).toBe(true);
    expect(awaitingWrite([message("user", "Who are you?")], REPLY, false)).toBe(true);
  });

  it("stops the moment the row lands", () => {
    expect(awaitingWrite(SETTLED, REPLY, false)).toBe(false);
  });

  it("keeps asking after a second turn on a settled thread", () => {
    expect(awaitingWrite(SETTLED, "A second, later reply.", false)).toBe(true);
  });

  it("does not ask when no turn produced any text", () => {
    // A provider that died before the first token persists nothing, so there is
    // nothing to wait for -- the error message is the whole story.
    expect(awaitingWrite(SETTLED, "", false)).toBe(false);
  });
});

describe("showDraft", () => {
  it("shows the caret as soon as the turn opens, before any token", () => {
    expect(showDraft([], "", true)).toBe(true);
  });

  it("shows the tokens arriving over an empty transcript", () => {
    expect(showDraft([], "I am", true)).toBe(true);
  });

  it("keeps showing after the stream closes, while the write is in flight", () => {
    expect(showDraft([message("user", "Who are you?")], REPLY, false)).toBe(true);
  });

  it("hides once the real assistant message is in the transcript", () => {
    // Otherwise the reply renders twice: once from the server, once from here.
    expect(showDraft(SETTLED, REPLY, false)).toBe(false);
  });

  it("keeps showing a second turn's reply over a stale settled transcript", () => {
    // The bug a last-role test would have shipped: the transcript still ends on
    // turn 1's assistant message, so "ends with assistant" would read as landed
    // and blank turn 2's reply.
    expect(showDraft(SETTLED, "A second, later reply.", false)).toBe(true);
  });

  it("stays hidden on a settled thread with no turn in flight", () => {
    expect(showDraft(SETTLED, "", false)).toBe(false);
  });
});

describe("transcriptPollMs", () => {
  it("asks fast while the write is expected", () => {
    expect(transcriptPollMs(0)).toBe(700);
    expect(transcriptPollMs(5)).toBe(700);
  });

  it("backs off rather than stopping", () => {
    expect(transcriptPollMs(12)).toBe(3_000);
    expect(transcriptPollMs(40)).toBe(15_000);
  });

  it("never stops, so a stalled write still resolves if the server moves", () => {
    expect(transcriptPollMs(10_000)).toBeGreaterThan(0);
  });
});
