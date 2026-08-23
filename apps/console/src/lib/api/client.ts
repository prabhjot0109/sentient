import { getAccessToken } from "@/lib/auth";

import { toApiError } from "./errors";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export type ApiInit = RequestInit & { skipAuth?: boolean };

function withAuth(init: RequestInit, token: string | null): RequestInit {
  const headers = new Headers(init.headers);
  if (token) headers.set("authorization", `Bearer ${token}`);
  return { ...init, headers };
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return typeof body?.detail === "string" ? body.detail : response.statusText;
  } catch {
    // A proxy or a crash can return HTML. Never let the error path throw its own
    // error -- that replaces a diagnosable 502 with an opaque SyntaxError.
    return response.statusText || `HTTP ${response.status}`;
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
  const response = await fetch(`${BASE_URL}${path}`, withAuth(rest, token));

  if (response.status !== 401 || skipAuth) return response;

  // Re-read the token ONCE. Not a loop: an expired session must not become a
  // request storm against Neon Auth, and the second 401 is the honest answer.
  // getAccessToken() goes through Better Auth's getSession(), so this picks up a
  // token minted since the first attempt; it does not force a refresh itself.
  const refreshed = await getAccessToken();
  return fetch(`${BASE_URL}${path}`, withAuth(rest, refreshed));
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
