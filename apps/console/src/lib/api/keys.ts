import type { ApiKey, CreatedApiKey } from "@/types/keys";

import { apiFetch } from "./client";

/** The raw row, before `revoked` is normalised. */
type ApiKeyRow = Omit<ApiKey, "revoked"> & { revoked: boolean | number };

/**
 * `revoked` is `INTEGER DEFAULT 0` in SQLite's `api_keys` and `boolean` in the
 * Postgres migration, so the same field arrives as 0/1 or as true/false depending
 * on which store is configured. Measured, not assumed. `!revoked` happens to work
 * on both; `revoked === true` silently never fires on SQLite, which is the shape
 * of bug that survives a demo. Normalised once here rather than in each component,
 * because three components normalising independently is how they come to disagree.
 */
const normalise = (row: ApiKeyRow): ApiKey => ({ ...row, revoked: Boolean(row.revoked) });

export const listKeys = () =>
  apiFetch<{ keys: ApiKeyRow[] }>("/v1/keys").then((r) => r.keys.map(normalise));

export const createKey = (label: string | null) =>
  apiFetch<CreatedApiKey>("/v1/keys", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ label }),
  });

export const revokeKey = (keyId: string) =>
  apiFetch<{ revoked: boolean }>(`/v1/keys/${keyId}`, { method: "DELETE" });
