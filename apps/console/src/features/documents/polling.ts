import type { SourceDocument } from "@/types/documents";
import { TERMINAL_STATUSES } from "@/types/documents";

/**
 * The upload state machine's stopping rule.
 *
 * `POST /v1/upload` answers 202 and returns no id, so the only truth about an
 * upload is the documents list. This decides when to keep asking.
 *
 * Deliberately NOT a deadline computed from `updated_at`: that compares the
 * server's clock to the browser's. H1 measured Neon's auth host running 2-3s
 * ahead of the API host, which 401'd every sign-in until `leeway=60` landed. A
 * browser clock a few minutes fast would mark every fresh upload stuck on sight.
 * Backing off instead needs no clock at all.
 */
export const shouldPoll = (docs: SourceDocument[] | undefined): boolean =>
  (docs ?? []).some((d) => !TERMINAL_STATUSES.includes(d.status));

/**
 * Whether a project-wide re-embed is in flight, read off the rows rather than
 * off `projects.status`.
 *
 * Both report it, and only this one is live. Nothing refetches
 * `projectKeys.detail(id)` on a timer -- `useProjectQuery` sets no
 * `refetchInterval` and `main.tsx` builds a bare `new QueryClient()` -- so a
 * banner keyed on the project status alone appears only after a window refocus
 * and never clears itself. `run_reindex_job` walks every row to `reindexing`
 * before it touches the project, and `shouldPoll` treats that as unsettled, so
 * this query is already polling for the whole window and both edges land on
 * their own.
 *
 * `processing` is deliberately excluded: that is a first-time ingest, which is
 * not a re-embed and must not raise the "NPCs answer 409" banner.
 */
export const hasReindexingDocument = (docs: SourceDocument[] | undefined): boolean =>
  (docs ?? []).some((d) => d.status === "reindexing");

const FAST_MS = 1_500;
const FAST_UNTIL = 20; // ~30s
const MEDIUM_MS = 5_000;
const MEDIUM_UNTIL = 44; // ~2min more
const SLOW_MS = 15_000;

/**
 * Widens the interval rather than stopping. A row stranded `processing` by a
 * crashed ingest job is only reconciled by H7's `fail_stuck_documents` AT
 * STARTUP, so it can genuinely sit forever while the process stays up -- but it
 * also resolves the instant the server moves, which a client that gave up would
 * never see. TanStack Query pauses interval refetching while the tab is hidden
 * (`refetchIntervalInBackground` defaults to false), so the slow tier costs
 * nothing in a backgrounded tab.
 */
export const pollIntervalMs = (completedFetches: number): number => {
  if (completedFetches < FAST_UNTIL) return FAST_MS;
  if (completedFetches < MEDIUM_UNTIL) return MEDIUM_MS;
  return SLOW_MS;
};
