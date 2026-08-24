import type { ProjectConfig } from "@/types/projects";

import { apiFetch } from "./client";

/**
 * The config fields a client may actually write.
 *
 * `embedding_signature` is on `ProjectConfig` because the backend reports it, but
 * it is DERIVED -- `update_config` recomputes it from the resolved runtime
 * settings after every write -- and it is not a field on `ConfigInput`, which is
 * `extra="forbid"`. Sending it is a 422. Excluding it here makes that a compile
 * error instead of a round trip.
 */
export type WritableConfigField = Exclude<keyof ProjectConfig, "embedding_signature">;

/**
 * A partial update. `ConfigInput` is `extra="forbid"` and the service applies
 * `model_dump(exclude_unset=True)`, so send ONLY what changed.
 *
 * An explicit `null` CLEARS a field -- that is how "reset to default" works, and
 * it is meaningfully different from omitting the key. `undefined` is dropped by
 * JSON.stringify, which gives us omit-vs-clear for free; do not "helpfully"
 * normalise undefined to null.
 */
export type ConfigPatch = Partial<Record<WritableConfigField, string | number | null>>;

/**
 * The PUT response is NOT the same shape as `ProjectDetail["config"]`.
 *
 * Measured 2026-08-24 against the live server: the detail's `config` carries 18
 * keys and the PUT carries 21 -- the same 18 plus `project_id`, `updated_at` and
 * `persona_prompt`. That last one is the STORED persona, where the detail
 * endpoint reports the RESOLVED one at its top level with a `persona_source`
 * beside it. Reusing `ProjectConfig` here would silently give the editor a
 * `persona_prompt` that means the opposite of the one next to it.
 */
export type StoredConfig = ProjectConfig & {
  project_id: string;
  persona_prompt: string | null;
  updated_at: string;
};

export const updateConfig = (projectId: string, patch: ConfigPatch) =>
  apiFetch<StoredConfig>(`/v1/projects/${projectId}/config`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(patch),
  });

/**
 * `PUT /v1/projects/{id}/persona`, not the `persona_prompt` field on the config
 * route. Two routes write the same column; this one is named for the job and
 * requires a `system_prompt`, so an empty body is a 422 rather than a silent
 * no-op. Confirmed: `{}` answers 422 `"Field required"`.
 *
 * It returns `StoredConfig`, NOT the project detail -- `services.projects.set_persona`
 * returns `upsert_project_config(...)`, the same 21-key row the config PUT gives
 * back. Measured 2026-08-24; the F3 plan had this as `ProjectDetail`. Nothing
 * reads the body, because the caller invalidates the detail query instead, but a
 * type that claims `persona_source` when the response has none is one refactor
 * away from a runtime undefined.
 */
export const setPersona = (projectId: string, systemPrompt: string) =>
  apiFetch<StoredConfig>(`/v1/projects/${projectId}/persona`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ system_prompt: systemPrompt }),
  });
