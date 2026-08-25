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
export class ServiceUnavailableError extends ApiError {}

export function toApiError(status: number, detail: string): ApiError {
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
