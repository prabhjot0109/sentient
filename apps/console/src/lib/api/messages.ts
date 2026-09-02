import {
  ApiError,
  ApiKeyLimitError,
  ConflictError,
  ForbiddenError,
  NetworkError,
  NotFoundError,
  ReindexInProgressError,
  ServiceUnavailableError,
  UnauthenticatedError,
  ValidationError,
} from "./errors";

export type ErrorTone = "info" | "warning" | "failure";

/** What a reader is shown. `tone` picks the colour; it is not a severity ranking. */
export type ErrorCopy = { title: string; body: string; tone: ErrorTone };

/**
 * The whole of F9's judgement, in the one place vitest can reach without a
 * browser. Components render an ErrorCopy and never branch on an error class,
 * so F11's restyle cannot accidentally change what a 409 means.
 *
 * Two rules this follows throughout:
 *
 * 1. NEVER render `error.message`. ApiError defines it as `${status}: ${detail}`,
 *    so nine call sites showed users "404: project not found" before F9.
 * 2. Where the backend wrote a sentence for a human, show that sentence. B4 went
 *    to real trouble to put Groq's own words in the 502 body, and F3+F4 flattened
 *    FastAPI's 422 array into `temperature: Input should be less than or equal
 *    to 2`. Generic copy over the top of either is a regression.
 */
export function describe(error: unknown): ErrorCopy {
  if (error instanceof NetworkError) {
    return {
      title: "Can't reach the Sentient API",
      body: "The server isn't answering. Check that it's running, then try again.",
      tone: "failure",
    };
  }

  if (error instanceof UnauthenticatedError) {
    return {
      title: "Your session has expired",
      body: "Sign in again to continue.",
      tone: "info",
    };
  }

  if (error instanceof ForbiddenError) {
    return {
      title: "You don't have access to this",
      body: "It belongs to another account.",
      tone: "failure",
    };
  }

  if (error instanceof NotFoundError) {
    return {
      title: "Not found",
      body: "It has been deleted, or it belongs to another account.",
      tone: "failure",
    };
  }

  if (error instanceof ApiKeyLimitError) {
    // The backend already wrote the numbers into its own sentence -- "you
    // already have 25 active API keys (limit 25); revoke one before creating
    // another" -- so covering it with generic copy would throw away the only
    // part the reader can act on. Rule 2, the same one B4's provider text and
    // F3+F4's flattened 422 follow.
    return {
      title: "You're at your API key limit",
      body: error.detail,
      tone: "warning",
    };
  }

  if (error instanceof ConflictError) {
    return {
      title: "That conflicts with the current state",
      body: error.detail,
      tone: "warning",
    };
  }

  if (error instanceof ReindexInProgressError) {
    // Not a failure: the rebuild is work in progress and it finishes on its own.
    // Measured under two seconds on a one-document project, so "try again in a
    // moment" is honest rather than optimistic. No "N of M" -- see the test.
    return {
      title: "Your lore is re-embedding",
      body: "Changing the embedding model rebuilds the index. Conversations resume as soon as it finishes — usually a few seconds.",
      tone: "warning",
    };
  }

  if (error instanceof ServiceUnavailableError) {
    return {
      title: "This feature isn't configured",
      body: error.detail,
      tone: "failure",
    };
  }

  if (error instanceof ValidationError) {
    return {
      title: "That won't work",
      body: error.detail,
      tone: "failure",
    };
  }

  if (error instanceof ApiError) {
    // Everything else, 502 included. B4 put the provider's own sentence in the
    // body precisely so it could be read here.
    return { title: "Something went wrong", body: error.detail, tone: "failure" };
  }

  return {
    title: "Something went wrong",
    body: "Try again. If it keeps happening, check the server logs.",
    tone: "failure",
  };
}

/**
 * The one failure that does not arrive as a thrown error.
 *
 * `projects.reindex_error` is a field on a *successful* response, because a
 * failed rebuild is a state the project is in rather than something that went
 * wrong with the request that asked about it. It still becomes words here, so
 * the two rules above hold in one place: nothing renders a raw status line, and
 * a sentence the backend wrote for a human is passed through rather than
 * covered.
 *
 * Returns null when there is nothing to report, so a caller renders the ordinary
 * "a rebuild is queued" banner instead. That distinction is the entire point of
 * the column: `projects.status = 'reindexing_required'` is written both when a
 * rebuild is enqueued and when one fails, so without a reason the console shows
 * a project that is about to be fine, forever.
 */
export function describeReindexFailure(reason: string | null | undefined): ErrorCopy | null {
  if (!reason) return null;
  return {
    title: "The last rebuild of this project failed",
    body: reason,
    tone: "failure",
  };
}
