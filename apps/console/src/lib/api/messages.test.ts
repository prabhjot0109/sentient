import { describe as suite, expect, it } from "vitest";

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
import { describe } from "./messages";

suite("describe", () => {
  it("tells a signed-out user to sign in again rather than showing a 401", () => {
    const copy = describe(new UnauthenticatedError(401, "authentication required"));
    expect(copy.title).toBe("Your session has expired");
    expect(copy.tone).toBe("info");
  });

  it("treats the reindex 409 as progress, not failure", () => {
    const copy = describe(
      new ReindexInProgressError(409, "project is reindexing; retrieval temporarily unavailable"),
    );
    expect(copy.title).toBe("Your lore is re-embedding");
    expect(copy.tone).toBe("warning");
  });

  it("does not send a user at the API-key cap to the reindex sentence", () => {
    // The bug this pins: 409 is answered by the reindex guard AND by the
    // per-user key cap, and mapping on status alone told someone who had run
    // out of key slots that their lore was re-embedding -- naming a subsystem
    // they were not touching.
    const copy = describe(
      new ApiKeyLimitError(409, "you already have 25 active API keys (limit 25); revoke one"),
    );
    expect(copy.title).toBe("You're at your API key limit");
    expect(copy.body).toContain("revoke one");
    expect(copy.body).not.toMatch(/re-embedding/i);
  });

  it("passes an unrecognised conflict's own sentence through", () => {
    const copy = describe(new ConflictError(409, "that name is already taken"));
    expect(copy.body).toBe("that name is already taken");
  });

  it("does not invent a progress fraction the backend never sends", () => {
    // The spec sketches "N of M done". No such number is on the wire:
    // services/chat.py raises one fixed sentence. The document rows carry the
    // real progress and F6 already polls them.
    const copy = describe(new ReindexInProgressError(409, "project is reindexing"));
    expect(copy.body).not.toMatch(/\d+\s*of\s*\d+/);
  });

  it("surfaces the backend's own sentence for a validation failure", () => {
    // F3+F4 fixed the seam so a 422 array flattens to a field-named sentence.
    // Replacing it with generic copy here would throw that away again.
    const copy = describe(
      new ValidationError(422, "temperature: Input should be less than or equal to 2"),
    );
    expect(copy.body).toContain("temperature: Input should be less than or equal to 2");
  });

  it("says which machine is unreachable for a transport failure", () => {
    const copy = describe(new NetworkError());
    expect(copy.title).toBe("Can't reach the Sentient API");
    expect(copy.tone).toBe("failure");
  });

  it("names the missing vault key for a 503", () => {
    const copy = describe(new ServiceUnavailableError(503, "credential vault is not configured"));
    expect(copy.body).toContain("credential vault is not configured");
  });

  it("distinguishes 403 from 404", () => {
    expect(describe(new ForbiddenError(403, "nope")).title).toBe("You don't have access to this");
    expect(describe(new NotFoundError(404, "project not found")).title).toBe("Not found");
  });

  it("never leaks the status prefix ApiError puts in .message", () => {
    // ApiError's message is `${status}: ${detail}`. Nine call sites rendered it
    // raw before F9, so users read "404: project not found".
    const copy = describe(new ApiError(502, "The model 'x' does not exist"));
    expect(copy.body).not.toMatch(/^\d{3}:/);
    expect(copy.body).toContain("The model 'x' does not exist");
  });

  it("handles a non-Error thrown value without throwing itself", () => {
    expect(describe("boom").tone).toBe("failure");
    expect(describe(undefined).title).toBe("Something went wrong");
  });
});
