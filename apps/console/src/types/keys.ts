/** Mirrors `src/sentient/api/routers/keys.py` and the `api_keys` table. */

export type ApiKey = {
  id: string;
  label: string | null;
  revoked: boolean;
  created_at: string | null;
};

/**
 * `GET /v1/keys`. `limit` is the per-user cap from `MAX_API_KEYS_PER_USER`, and
 * `0` means uncapped -- matching the `if limit > 0` guard the POST applies. It is
 * reported so the console can refuse the key that would 409 rather than letting
 * the user discover the ceiling by hitting it.
 *
 * Revoked rows still count as rows here and NOT against the cap: revoking is how
 * a user makes room, so the two counts are deliberately different numbers.
 */
export type ApiKeyList = {
  keys: ApiKey[];
  limit: number;
};

/**
 * The response to `POST /v1/keys`. `api_key` is the ONLY time the raw key exists
 * outside the client's memory: `generate_api_key()` (`adapters/auth.py`) returns
 * (raw, sha256) and only the hash is stored, so `GET /v1/keys` can never return
 * it again and neither can support.
 */
export type CreatedApiKey = {
  id: string;
  api_key: string;
  label: string | null;
};
