import type { ChatMessage } from "@/types/threads";

/**
 * Whether the reply the browser just streamed is now in the transcript.
 *
 * Exact, not a heuristic: `openai_wire.astream_completion` persists
 * `"".join(parts)` built from the very strings it yielded as `delta.content`,
 * with no strip and no post-processing, so the accumulated draft and the stored
 * row are byte-identical. That is what makes content equality sound here where a
 * message count or a `created_at` comparison would not be -- a count is stale
 * across turns and a timestamp compares the server's clock to the browser's,
 * which H1 measured running 2-3 s apart.
 */
export const draftLanded = (messages: ChatMessage[] | undefined, draft: string): boolean =>
  draft !== "" && (messages ?? []).some((m) => m.role === "assistant" && m.content === draft);

/**
 * Whether the deferred transcript write is still outstanding, and therefore
 * whether to keep asking for it.
 *
 * This exists because of a measurement, not a guess. `POST /v1/chat` writes both
 * messages through `defer()`, so they land AFTER the response body closes.
 * Measured 2026-08-23 on groq / openai/gpt-oss-20b against the live Neon branch,
 * three trials: at the earliest moment a client could possibly ask -- 406 ms
 * after `[DONE]` -- the transcript read **zero messages** in two of three, and
 * the assistant row did not appear until **1.3-1.7 s** after the stream closed.
 * A single invalidate fired on `[DONE]`, which is what the F5 plan specified,
 * therefore refetches an empty list essentially every turn, and the reply the
 * user just watched arrive disappears.
 *
 * Nothing is asked for during the stream itself: a stream is a push, the
 * transcript cannot change while it runs, and this window is only ever the tail.
 */
export const awaitingWrite = (
  messages: ChatMessage[] | undefined,
  draft: string,
  isStreaming: boolean,
): boolean => !isStreaming && draft !== "" && !draftLanded(messages, draft);

/**
 * Whether to render the provisional assistant bubble.
 *
 * The draft is UI for a reply that is not in the transcript yet, so it is shown
 * exactly while that is true. Both neighbouring bugs are closed by the same
 * line: dropping it at end-of-stream blanks the reply for the 1.3-1.7 s the
 * write takes, and keeping it after the refetch renders the same sentence twice,
 * once from the server and once from here.
 */
export const showDraft = (
  messages: ChatMessage[] | undefined,
  draft: string,
  isStreaming: boolean,
): boolean => isStreaming || awaitingWrite(messages, draft, isStreaming);

const FAST_MS = 700;
const FAST_UNTIL = 10; // ~7s, comfortably past the measured 1.7s worst case
const MEDIUM_MS = 3_000;
const MEDIUM_UNTIL = 30; // ~1min more
const SLOW_MS = 15_000;

/**
 * Widens the interval rather than stopping, for the same reason F6's does: a
 * write that never committed is only ever reconciled if the client is still
 * asking when the server moves. TanStack pauses interval refetching while the
 * tab is hidden (`refetchIntervalInBackground` defaults to false), so the slow
 * tier costs nothing in a backgrounded tab.
 *
 * Driven by TanStack's own `dataUpdateCount`, so there is no counter to keep and
 * a remount behaves correctly.
 */
export const transcriptPollMs = (completedFetches: number): number => {
  if (completedFetches < FAST_UNTIL) return FAST_MS;
  if (completedFetches < MEDIUM_UNTIL) return MEDIUM_MS;
  return SLOW_MS;
};
