import type { StoredCredential, StoredCredentialAck } from "@/types/credentials";

import { apiFetch } from "./client";

/**
 * All three of these answer 503 when `SENTIENT_SECRET_KEY` is unset -- including
 * this GET. Measured 2026-08-24 on a deployment with no vault key: all four calls
 * (list, store, store-with-a-bad-provider, delete) returned
 * `503 {"detail":"credential vault is not configured"}`, and the bad provider
 * returned 503 rather than 400, because `store_credential` gates on the vault
 * BEFORE it validates the provider.
 *
 * A vault that cannot be listed is not an empty vault, and the two lead to
 * opposite next actions, so the caller must distinguish them.
 * `lib/api/errors.ts` maps 503 to ServiceUnavailableError.
 */
export const listCredentials = () =>
  apiFetch<{ credentials: StoredCredential[] }>("/v1/credentials").then((r) => r.credentials);

/**
 * Replaces any existing key for this provider: UNIQUE(user_id, provider).
 * Measured -- a second POST for `google` left one row, with the new hint.
 *
 * Answers a two-field ack, not a vault row. See `StoredCredentialAck`.
 */
export const storeCredential = (provider: string, apiKey: string) =>
  apiFetch<StoredCredentialAck>("/v1/credentials", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ provider, api_key: apiKey }),
  });

/**
 * The PROVIDER is the path segment -- there is no credential id. Deleting one
 * that is not there is `200 {"deleted": false}`, not a 404; an unsupported
 * provider name is a 400.
 */
export const deleteCredential = (provider: string) =>
  apiFetch<{ deleted: boolean }>(`/v1/credentials/${encodeURIComponent(provider)}`, {
    method: "DELETE",
  });
