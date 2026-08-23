import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "@/lib/api/threads";

import { awaitingWrite, transcriptPollMs } from "./transcript";

/** One factory, so no two call sites can invalidate slightly different keys. */
export const threadKeys = {
  all: (projectId: string) => ["threads", projectId] as const,
  messages: (threadId: string) => ["messages", threadId] as const,
};

export const useThreadsQuery = (projectId: string) =>
  useQuery({
    queryKey: threadKeys.all(projectId),
    queryFn: () => api.listThreads(projectId),
    // A 404 here means the project is not this user's. It does not improve on a
    // retry, and retrying turns a clean "not found" into three seconds of spinner.
    retry: false,
  });

/**
 * The transcript, plus the one window in which it has to be chased.
 *
 * `enabled` rather than a conditional hook: React forbids calling a hook
 * conditionally, and the chat screen legitimately has no thread selected on a
 * fresh project.
 *
 * `pendingDraft` is the reply the browser has streamed but not yet seen come
 * back. While that is outstanding this query polls, because both messages are
 * written through `defer()` and land 1.3-1.7 s AFTER the stream closes -- see
 * `transcript.ts` for the measurement. It stops on its own the moment the row
 * appears; there is no timer to cancel and no deadline computed from a clock.
 */
export const useMessagesQuery = (threadId: string | null, pendingDraft = "", isStreaming = false) =>
  useQuery({
    queryKey: threadKeys.messages(threadId ?? "none"),
    queryFn: () => api.listMessages(threadId as string),
    enabled: threadId !== null,
    refetchInterval: (query) =>
      awaitingWrite(query.state.data, pendingDraft, isStreaming)
        ? transcriptPollMs(query.state.dataUpdateCount)
        : false,
    retry: false,
  });

export const useRenameThreadMutation = (projectId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => api.renameThread(id, title),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: threadKeys.all(projectId) }),
  });
};

export const useDeleteThreadMutation = (projectId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteThread(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: threadKeys.all(projectId) });
      // The message cache for a deleted thread is not stale, it is wrong. Left in
      // place, reselecting that id renders a dead transcript before the refetch
      // 404s.
      queryClient.removeQueries({ queryKey: threadKeys.messages(id) });
    },
  });
};
