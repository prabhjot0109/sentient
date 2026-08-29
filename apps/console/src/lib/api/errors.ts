/**
 * Mirrors src/sentient/core/errors.py. One class per status the backend actually
 * returns, so F9 can render a real UI per case instead of one generic failure.
 */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(`${status}: ${detail}`);
    this.name = new.target.name;
  }
}

export class ValidationError extends ApiError {}
export class UnauthenticatedError extends ApiError {}
export class ForbiddenError extends ApiError {}
export class NotFoundError extends ApiError {}
/** The reindex guard. Deserves specific treatment: "your lore is re-embedding", not a failure. */
export class ReindexInProgressError extends ApiError {}
/** The per-user cap in `routers/keys.py`. A 409, and nothing to do with reindexing. */
export class ApiKeyLimitError extends ApiError {}
/** Any other 409. Named so the two above are not the only shapes a conflict can take. */
export class ConflictError extends ApiError {}
export class ServiceUnavailableError extends ApiError {}

/**
 * TWO 409s, and they mean opposite things.
 *
 * The reindex guard answers 409 ("wait, it finishes on its own") and so does the
 * API-key cap ("revoke a key you are not using"). Mapping the status alone sent
 * every user who ran out of key slots to "Your lore is re-embedding", which is
 * not merely unhelpful -- it names a subsystem they were not touching.
 *
 * `code` comes from the backend's `X-Error-Code` header (`core/errors.py` owns
 * the strings). It is OPTIONAL, and the fallback is deliberate: a 409 with no
 * code is treated as the reindex case, which is what every 409 meant before the
 * header existed. So an older backend, or one behind a proxy that strips the
 * header, keeps today's behaviour rather than degrading to a generic failure.
 */
export function toApiError(status: number, detail: string, code?: string | null): ApiError {
  switch (status) {
    case 400:
    case 422:
      return new ValidationError(status, detail);
    case 401:
      return new UnauthenticatedError(status, detail);
    case 403:
      return new ForbiddenError(status, detail);
    case 404:
      return new NotFoundError(status, detail);
    case 409:
      if (code === "api_key_limit") return new ApiKeyLimitError(status, detail);
      if (code && code !== "reindex_in_progress") return new ConflictError(status, detail);
      return new ReindexInProgressError(status, detail);
    case 503:
      return new ServiceUnavailableError(status, detail);
    default:
      return new ApiError(status, detail);
  }
}

/**
 * The backend was never reached: process down, DNS gone, or a CORS preflight
 * refused. fetch rejects with `TypeError: Failed to fetch`, which never passes
 * through toApiError, so before this it arrived at components as an untyped
 * Error and rendered as the generic "Something went wrong." branch -- i.e. the
 * one state F9 is named after was the one state the seam could not type.
 *
 * status 0 is what XMLHttpRequest reports for the same condition. It cannot
 * collide with a real HTTP status, and staying inside ApiError means no call
 * site has to widen its type.
 */
export class NetworkError extends ApiError {
  constructor(detail = "Could not reach the Sentient API.") {
    super(0, detail);
  }
}
