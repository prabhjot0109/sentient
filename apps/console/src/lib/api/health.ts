import { apiFetch } from "./client";

/**
 * Mirrors the bare dict returned by `src/sentient/api/routers/health.py`. That
 * route has no Pydantic schema, so this is the only written-down copy of its
 * shape -- keep the two in step.
 */
export type HealthResponse = {
  status: string;
  brain_loaded: boolean;
  index_loaded: boolean;
  source_count: number;
  llm_provider: string;
  llm_model: string;
  embedding_provider: string;
  embedding_model: string;
  search_type: string;
  top_k: number;
  persona: string | null;
  index_metadata: Record<string, unknown> | null;
};

/**
 * Unauthenticated on purpose: this is the "is the backend up" probe the shell
 * shows before a session exists.
 */
export const getHealth = () => apiFetch<HealthResponse>("/health", { skipAuth: true });
