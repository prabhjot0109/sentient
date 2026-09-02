/**
 * Mirrors `src/sentient/api/schemas/projects.py` and the `projects` /
 * `project_configs` tables.
 */

/** A row of the backend's `projects` table. */
export type Project = {
  id: string;
  user_id?: string;
  name: string;
  base_preset: string;
  status: string;
  /**
   * Optional because the two stores disagree. `PostgresStateStore.list_projects`
   * selects `id, name, base_preset, status` and only ORDERS BY `created_at`, and
   * neither store returns it from `create_project`. SQLite's `SELECT *` does.
   * Rendering a project's created date would therefore work on SQLite and show
   * nothing on Neon, so nothing renders it.
   */
  created_at?: string | null;
  /**
   * Why the last rebuild failed, or null. Returned by BOTH stores from
   * `get_project`, `list_projects` and `create_project` -- verified against the
   * column lists rather than assumed, because `created_at` above is the
   * cautionary tale of a field only one of them returns.
   *
   * It exists because `status` carries two meanings. `reindexing_required` is
   * written both by `update_config` ("a rebuild is queued") and by
   * `run_reindex_job`'s except ("a rebuild failed"), so without a reason the
   * console shows a project that is about to be fine, forever. A reason rather
   * than a second status: nothing that switches on `status` grows a case, and a
   * retry is still the ordinary path back.
   */
  reindex_error?: string | null;
};

/**
 * Every field is nullable BY DESIGN: null means "unset", not "the default happens
 * to be this". `get_project_detail` reports the config as STORED for exactly this
 * reason -- F3 has to tell the two apart, because rendering a resolved default
 * into an input pins a value the user never chose. Derived from `_CONFIG_COLUMNS`
 * in `adapters/state/schema.py`, minus `persona_prompt`, which is reported
 * separately because it resolves through the preset fallback and these do not.
 */
export type ProjectConfig = {
  llm_provider: string | null;
  embedding_provider: string | null;
  model_name: string | null;
  embedding_model_name: string | null;
  temperature: number | null;
  max_tokens: number | null;
  mrl_vector_size: number | null;
  reasoning_effort: string | null;
  reasoning_format: string | null;
  rag_search_type: string | null;
  rag_top_k: number | null;
  rag_fetch_k: number | null;
  rag_mmr_lambda: number | null;
  rag_score_threshold: number | null;
  rag_chunk_size: number | null;
  rag_chunk_overlap: number | null;
  history_window: number | null;
  embedding_signature: string | null;
};

/**
 * Which of the three sources the persona the NPC actually speaks with came from.
 * H1's Finding 4 measured a project whose stored `persona_prompt` was NULL while
 * the NPC visibly had one from its preset; an editor reading the stored value
 * alone renders a blank field over a live persona and overwrites it on save.
 */
export type PersonaSource = "custom" | "preset" | "generic";

/** `GET /v1/projects/{id}` -- the project, its stored config, the resolved persona. */
export type ProjectDetail = Project & {
  config: ProjectConfig;
  persona_prompt: string;
  persona_source: PersonaSource;
};

/** The one status that makes the chat and retrieval paths answer 409. */
export const REINDEXING = "reindexing_required";
