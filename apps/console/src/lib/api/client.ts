import { getAccessToken } from "@/lib/auth";

import { NetworkError, toApiError } from "./errors";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export type ApiInit = RequestInit & { skipAuth?: boolean };

function withAuth(init: RequestInit, token: string | null): RequestInit {
  const headers = new Headers(init.headers);
  if (token) headers.set("authorization", `Bearer ${token}`);
  return { ...init, headers };
}

/** One entry of FastAPI's request-validation array. */
type ValidationDetail = { loc?: unknown[]; msg?: string };

/**
 * FastAPI answers a request-validation failure with `detail` as an ARRAY of error
 * objects rather than a string:
 *
 *   [{"type":"less_than_equal","loc":["body","temperature"],
 *     "msg":"Input should be less than or equal to 2","input":5}]
 *
 * Read as "not a string" it fell through to `statusText` -- "Unprocessable
 * Content" -- which tells the user nothing about which of seventeen fields was
 * out of range. Flattened here, at the one place that turns a status into an
 * error, rather than in whichever form happened to notice first.
 *
 * `loc[0]` is the request part (`body`, `query`, `path`) and is dropped: the
 * field name is what the reader can act on, and it is what sits beside the input
 * that produced it.
 */
function flattenValidation(detail: ValidationDetail[]): string {
  return detail
    .map((entry) => {
      const field = Array.isArray(entry.loc) ? entry.loc.slice(1).join(".") : "";
      const message = entry.msg ?? "is invalid";
      return field ? `${field}: ${message}` : message;
    })
    .join("; ");
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail) && body.detail.length > 0) {
      return flattenValidation(body.detail);
    }
    return response.statusText;
  } catch {
    // A proxy or a crash can return HTML. Never let the error path throw its own
    // error -- that replaces a diagnosable 502 with an opaque SyntaxError.
    return response.statusText || `HTTP ${response.status}`;
  }
}

/**
 * Only a TypeError is a transport failure. A ReferenceError or a TypeError we
 * threw ourselves further up must keep propagating: reporting our own bug as
 * "the backend is unreachable" is a plausible lie, and it sends the reader to
 * the wrong machine.
 */
async function send(path: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(`${BASE_URL}${path}`, init);
  } catch (cause) {
    if (cause instanceof TypeError) throw new NetworkError();
    throw cause;
  }
}

/**
 * The seam. The ONLY place an Authorization header is attached, a 401 triggers a
 * re-read of the token, or an HTTP status becomes a typed error. Features import
 * a resource module and never call fetch -- lint enforces that, because
 * bypassing this silently loses all three behaviours.
 */
async function request(path: string, init: ApiInit = {}): Promise<Response> {
  const { skipAuth, ...rest } = init;
  const token = skipAuth ? null : await getAccessToken();
  const response = await send(path, withAuth(rest, token));

  if (response.status !== 401 || skipAuth) return response;

  // Re-read the token ONCE. Not a loop: an expired session must not become a
  // request storm against Neon Auth, and the second 401 is the honest answer.
  // getAccessToken() goes through Better Auth's getSession(), so this picks up a
  // token minted since the first attempt; it does not force a refresh itself.
  const refreshed = await getAccessToken();
  return send(path, withAuth(rest, refreshed));
}

export async function apiFetch<T>(path: string, init: ApiInit = {}): Promise<T> {
  const response = await request(path, init);
  if (!response.ok) throw toApiError(response.status, await readDetail(response));
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * The same seam, returning the raw Response so the caller can read `body` as a
 * stream. Used by F8: SSE is read with fetch + a ReadableStream reader, never
 * EventSource, which cannot POST and cannot set an Authorization header.
 */
export async function apiStream(path: string, init: ApiInit = {}): Promise<Response> {
  const response = await request(path, init);
  if (!response.ok) throw toApiError(response.status, await readDetail(response));
  return response;
}
