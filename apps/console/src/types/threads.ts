/**
 * Mirrors `chat_threads` / `chat_messages` and `src/sentient/api/schemas/`.
 * These two tables are the ONE durable memory for both surfaces (G4): a thread
 * here may have been written by Mantella in Skyrim or by this console.
 */

/**
 * A row of `chat_threads`, as `GET /v1/projects/{id}/threads` returns it.
 *
 * `prefix_hash` is DELIBERATELY ABSENT even though two of the four paths that
 * return a thread do include it. Measured 2026-08-23 against the live Neon
 * branch and a temporary SQLite store:
 *
 *   | path                        | Postgres | SQLite |
 *   | list_threads (this one)     | absent   | present |
 *   | rename_thread (PATCH's 200) | PRESENT  | present |
 *
 * So it is not one store disagreeing with the other -- Postgres disagrees with
 * ITSELF, because `list_threads` names its columns and `rename_thread` names a
 * different set. It is G4's internal thread-identity mechanism, the hash of the
 * conversation prefix Mantella resends, and it means nothing to a reader.
 * Typing it as optional would invite someone to render or branch on a field
 * that is null, missing, or a 64-char hash depending on which call filled it
 * in. Do not add it back.
 */
export type Thread = {
  /** Postgres: dashed UUID. SQLite: bare hex. A React key, nothing more. */
  id: string;
  project_id: string;
  /**
   * The discriminator between the two kinds of thread. Set by the game path;
   * `null` for a thread this console created. Without it the sidebar reads as a
   * pile of untitled conversations.
   */
  npc_name: string | null;
  session_id: string;
  /**
   * `null` is real, and common: a game thread has no title at all. The console
   * sets it to the first message truncated to 60 characters.
   */
  title: string | null;
  created_at: string;
  updated_at: string;
};

/** A row of `chat_messages`. Both stores return these nine fields identically. */
export type ChatMessage = {
  id: string;
  thread_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  /**
   * These four are nullable BY DESIGN (H4): a user message has no usage, and some
   * providers report none. A default of 0 would turn missing telemetry into a
   * real-looking zero in every sum built on it -- so render an em dash, never 0.
   */
  model: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
};

/** One retrieved chunk, as the `sentient.chat.meta` frame carries it. */
export type RetrievedChunk = {
  content: string;
  score: number | null;
  source: string;
  page_label: string;
  chunk_id: number | null;
};
