import type { ConfigPatch, WritableConfigField } from "@/lib/api/config";
import type { ProjectConfig } from "@/types/projects";

/**
 * The three fields that feed the embedding signature, and therefore the only
 * three that can trigger a project-wide re-embed.
 *
 *   embedding_signature = sha256(f"{provider}|{model}|{size or 'default'}")[:16]
 *
 * `update_config` compares it before and after and, on a change, sets the project
 * to `reindexing_required` and enqueues the job. Nothing else in the seventeen
 * fields touches it -- verified by measurement, not by reading: a PUT of
 * `{"temperature":0.4,"rag_top_k":8}` left the signature byte-identical, and a
 * PUT of `{"mrl_vector_size":768}` moved it.
 */
export const EMBEDDING_FIELDS = [
  "embedding_provider",
  "embedding_model_name",
  "mrl_vector_size",
] as const satisfies readonly WritableConfigField[];

/**
 * Whether saving this patch is LIKELY to re-embed the project.
 *
 * A prediction, not a fact. The signature is computed from the RESOLVED runtime
 * settings, so clearing a field falls through to an `.env` default the browser
 * cannot see and may produce the same signature after all. The server's answer is
 * the `embedding_signature` in the PUT response; this only decides whether to
 * warn first.
 *
 * Erring towards warning is deliberate: a warning that turns out unnecessary
 * costs a dialog, a missing one costs a silent re-embed of somebody's library.
 *
 * Note what this deliberately does NOT do: read `project.status`. Measured
 * 2026-08-24 on a one-document project, the status flipped to
 * `reindexing_required` and back to `active` inside two seconds, and on an empty
 * project the flip was never observable at all. Nothing refetches the project
 * detail on a timer either (see apps/console/AGENTS.md), so a status read is
 * both too slow and too late. The patch and the stored config are the inputs.
 */
export const willReindex = (patch: ConfigPatch, current: ProjectConfig): boolean =>
  EMBEDDING_FIELDS.some((field) => field in patch && patch[field] !== current[field]);
