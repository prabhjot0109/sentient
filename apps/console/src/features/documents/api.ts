import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "@/lib/api/documents";

import { pollIntervalMs, shouldPoll } from "./polling";

/**
 * One factory, so no two call sites can invalidate slightly different keys. That
 * bug presents as "the list didn't update" and costs an hour to find.
 */
export const documentKeys = {
  all: (projectId: string) => ["documents", projectId] as const,
};

/**
 * The state machine. `POST /v1/upload` returns 202 with no id, so this query is
 * the only place the truth about an upload lives.
 *
 * `dataUpdateCount` is TanStack's own count of successful fetches for this query,
 * which is why the backoff needs no counter of its own and survives a remount
 * correctly (a fresh mount of a settled project starts at 0, sees no unsettled
 * row, and never schedules a poll at all).
 */
export const useDocumentsQuery = (projectId: string) =>
  useQuery({
    queryKey: documentKeys.all(projectId),
    queryFn: () => api.listDocuments(projectId),
    refetchInterval: (query) =>
      shouldPoll(query.state.data) ? pollIntervalMs(query.state.dataUpdateCount) : false,
    // A 404 here means the project is not this user's. It does not improve on a
    // retry, and retrying turns a clean "not found" into three seconds of spinner.
    retry: false,
  });

export const useUploadDocumentMutation = (projectId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => api.uploadDocument(projectId, file),
    // Refetch rather than write an optimistic row: the 202 carries the SANITISED
    // filename and nothing else, so a hand-built row would have to invent
    // `id`, `size_bytes` and both timestamps. One extra round trip beats four
    // guesses, three of which the list renders.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: documentKeys.all(projectId) }),
  });
};

export const useDeleteDocumentMutation = (projectId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (filename: string) => api.deleteDocument(projectId, filename),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: documentKeys.all(projectId) }),
  });
};
