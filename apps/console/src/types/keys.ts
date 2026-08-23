/** Mirrors `src/sentient/api/routers/keys.py` and the `api_keys` table. */

export type ApiKey = {
  id: string;
  label: string | null;
  revoked: boolean;
  created_at: string | null;
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
