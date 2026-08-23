import type { ChatMessage, Thread } from "@/types/threads";

import { apiFetch } from "./client";

/**
 * Ordered `updated_at DESC, id DESC` by BOTH stores -- most recent first, which
 * is the order the sidebar wants. Do not re-sort client-side; a second sort on a
 * nullable timestamp is how the order silently becomes non-deterministic.
 */
export const listThreads = (projectId: string) =>
  apiFetch<{ threads: Thread[] }>(`/v1/projects/${projectId}/threads`).then((r) => r.threads);

/**
 * Chronological. Both stores select a newest-first window of `limit` and then
 * re-sort ascending, so this is the render order.
 *
 * `limit` is bounded 1..200 server-side; outside it the route answers 422. The
 * default of 50 matches the backend's.
 */
export const listMessages = (threadId: string, limit = 50) =>
  apiFetch<{ messages: ChatMessage[] }>(`/v1/threads/${threadId}/messages?limit=${limit}`).then(
    (r) => r.messages,
  );

/**
 * The 200 body carries `prefix_hash` on both stores, unlike the list. It is not
 * in `Thread` on purpose (see the type's own comment) and nothing here strips
 * it: TypeScript ignores the extra key and no caller can reach it.
 */
export const renameThread = (threadId: string, title: string) =>
  apiFetch<Thread>(`/v1/threads/${threadId}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ title }),
  });

export const deleteThread = (threadId: string) =>
  apiFetch<{ deleted: boolean }>(`/v1/threads/${threadId}`, { method: "DELETE" });
