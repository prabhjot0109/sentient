/** Mirrors `provider_credentials` and `src/sentient/api/schemas/credentials.py`. */

/**
 * The `Provider` Literal in `src/sentient/core/config.py`, which is also the
 * `_CREDENTIAL_PROVIDERS` set in `services/credentials.py`. A value outside it is
 * a 422 from the config route and a 400 "unknown provider" from the vault, which
 * is why every provider control is a select and never free text.
 */
export const PROVIDERS = [
  "google",
  "openai",
  "huggingface",
  "groq",
  "cerebras",
  "openrouter",
] as const;
export type Provider = (typeof PROVIDERS)[number];

/** The `SearchType` Literal in the same file. */
export const SEARCH_TYPES = ["similarity", "mmr"] as const;

/**
 * One row of the vault, as `GET /v1/credentials` returns it.
 *
 * There is NO `id` and no key material. Both stores select exactly
 * `provider, key_hint, created_at` explicitly -- neither uses SELECT * -- so
 * `encrypted_key` never leaves the process on either backend. Checked
 * deliberately on 2026-08-24 against Neon, because this is the one store
 * divergence that would have been a security bug rather than a rendering one:
 * the listing was grepped for the plaintext that had just been stored and for
 * `encrypted_key`, and matched neither.
 *
 * The PROVIDER is the identity: `provider_credentials` is UNIQUE(user_id,
 * provider), so storing a second key for a provider replaces the first --
 * measured, one row with the new hint -- and DELETE takes the provider name as
 * its path segment.
 */
export type StoredCredential = {
  provider: string;
  /**
   * A few characters of the original, for recognition. Never the key.
   *
   * **It already carries its own leading ellipsis.** `core/crypto.key_hint` is
   * `"…" + raw[-4:]`, so a stored `sk-…ABCD` arrives as the five-character string
   * `"…ABCD"`. Rendering it as `…{key_hint}` prints `……ABCD`; render it raw.
   */
  key_hint: string | null;
  created_at: string;
};

/**
 * What `POST /v1/credentials` answers -- and it is NOT a `StoredCredential`.
 *
 * The service returns `{"provider": ..., "key_hint": ...}` and stops there;
 * `created_at` is on the listing only. Measured 2026-08-24. Nothing reads this
 * body (the mutation invalidates and refetches instead), but typing it as the
 * three-field row would put a `created_at` in the type that is `undefined` at
 * runtime, which is exactly the class of bug the store-divergence rule exists for.
 */
export type StoredCredentialAck = Pick<StoredCredential, "provider" | "key_hint">;
