import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getAccessToken = vi.fn();
vi.mock("@/lib/auth", () => ({ getAccessToken: () => getAccessToken() }));

import { apiFetch } from "./client";
import {
  NetworkError,
  NotFoundError,
  ReindexInProgressError,
  UnauthenticatedError,
} from "./errors";

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("apiFetch", () => {
  beforeEach(() => {
    getAccessToken.mockReset();
    getAccessToken.mockResolvedValue("token-1");
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => vi.unstubAllGlobals());

  it("attaches the bearer token", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(200, { projects: [] }));
    await apiFetch("/v1/projects");
    const headers = new Headers(vi.mocked(fetch).mock.calls[0][1]!.headers);
    expect(headers.get("authorization")).toBe("Bearer token-1");
  });

  it("sends no authorization header when signed out", async () => {
    getAccessToken.mockResolvedValue(null);
    vi.mocked(fetch).mockResolvedValue(jsonResponse(200, {}));
    await apiFetch("/v1/projects");
    const headers = new Headers(vi.mocked(fetch).mock.calls[0][1]!.headers);
    expect(headers.has("authorization")).toBe(false);
  });

  it("refreshes once and retries on a 401", async () => {
    getAccessToken.mockResolvedValueOnce("stale").mockResolvedValueOnce("fresh");
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(401, { detail: "authentication required" }))
      .mockResolvedValueOnce(jsonResponse(200, { projects: [] }));

    await expect(apiFetch("/v1/projects")).resolves.toEqual({ projects: [] });
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(2);
    const retryHeaders = new Headers(vi.mocked(fetch).mock.calls[1][1]!.headers);
    expect(retryHeaders.get("authorization")).toBe("Bearer fresh");
  });

  it("retries a 401 exactly once, then throws", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(401, { detail: "authentication required" }));
    await expect(apiFetch("/v1/projects")).rejects.toBeInstanceOf(UnauthenticatedError);
    // Two calls total, never a loop: an expired session must not become a
    // request storm against Neon Auth.
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(2);
  });

  it("maps status onto typed errors", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(404, { detail: "project not found" }));
    await expect(apiFetch("/v1/projects/x")).rejects.toBeInstanceOf(NotFoundError);

    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(409, { detail: "project is reindexing; retrieval temporarily unavailable" }),
    );
    await expect(apiFetch("/v1/chat")).rejects.toBeInstanceOf(ReindexInProgressError);
  });

  it("carries the backend detail string onto the error", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(403, { detail: "project not found for this key" }),
    );
    await expect(apiFetch("/v1/x")).rejects.toMatchObject({
      status: 403,
      detail: "project not found for this key",
    });
  });

  // FastAPI answers a request-validation failure with `detail` as an ARRAY of
  // error objects, not a string. Every screen before F3 produced string details
  // almost exclusively; F3's config form has seventeen bounded fields and is the
  // first surface that hits the array shape routinely. Measured 2026-08-24:
  // PUT /config {"temperature":5} -> 422 with the array below.
  it("flattens a FastAPI validation array into a readable sentence", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(422, {
        detail: [
          {
            type: "less_than_equal",
            loc: ["body", "temperature"],
            msg: "Input should be less than or equal to 2",
            input: 5,
          },
        ],
      }),
    );
    await expect(apiFetch("/v1/projects/x/config")).rejects.toMatchObject({
      status: 422,
      detail: "temperature: Input should be less than or equal to 2",
    });
  });

  it("joins several validation errors instead of surfacing only the first", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(422, {
        detail: [
          { loc: ["body", "temperature"], msg: "Input should be less than or equal to 2" },
          { loc: ["body", "rag_top_k"], msg: "Input should be greater than or equal to 1" },
        ],
      }),
    );
    await expect(apiFetch("/v1/projects/x/config")).rejects.toMatchObject({
      detail:
        "temperature: Input should be less than or equal to 2; " +
        "rag_top_k: Input should be greater than or equal to 1",
    });
  });

  it("drops the leading body/query segment rather than printing it", async () => {
    // `loc` is ["body", "<field>"] for a JSON body. Naming the field alone is
    // what makes the message usable next to the input that produced it.
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(422, {
        detail: [{ loc: ["body"], msg: "Input should be a valid dictionary" }],
      }),
    );
    await expect(apiFetch("/v1/x")).rejects.toMatchObject({
      detail: "Input should be a valid dictionary",
    });
  });

  it("handles a non-JSON error body without throwing a parse error", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("<html>502</html>", { status: 502 }));
    await expect(apiFetch("/v1/x")).rejects.toMatchObject({ status: 502 });
  });

  it("does not send a token when skipAuth is set", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(200, { status: "ok" }));
    await apiFetch("/health", { skipAuth: true });
    expect(getAccessToken).not.toHaveBeenCalled();
  });

  it("does not leak skipAuth into the outgoing RequestInit", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(200, {}));
    await apiFetch("/health", { skipAuth: true });
    expect(vi.mocked(fetch).mock.calls[0][1]).not.toHaveProperty("skipAuth");
  });

  it("returns undefined on a 204 rather than choking on an empty body", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
    await expect(apiFetch("/v1/threads/x")).resolves.toBeUndefined();
  });
});

describe("transport failures", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("turns a dead backend into a typed NetworkError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(apiFetch("/v1/projects")).rejects.toBeInstanceOf(NetworkError);
  });

  it("gives the NetworkError status 0 so it cannot collide with an HTTP status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(apiFetch("/v1/projects")).rejects.toMatchObject({ status: 0 });
  });

  it("does not swallow a programming error thrown inside the seam", async () => {
    // A ReferenceError from our own code must NOT be reported to the user as
    // "the backend is unreachable" -- that hides the bug behind a plausible
    // network story and sends the reader looking at the wrong machine.
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new ReferenceError("x is not defined")));

    await expect(apiFetch("/v1/projects")).rejects.toBeInstanceOf(ReferenceError);
  });
});
