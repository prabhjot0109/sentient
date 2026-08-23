import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { streamChat } from "@/lib/api/chat";
import { ApiError, ReindexInProgressError } from "@/lib/api/errors";
import type { RetrievedChunk } from "@/types/threads";

import {
  threadKeys,
  useDeleteThreadMutation,
  useMessagesQuery,
  useRenameThreadMutation,
  useThreadsQuery,
} from "./api";

/** The feature's public verbs. Components call these and never reach lib/api. */
export const useThreads = useThreadsQuery;
export const useMessages = useMessagesQuery;
export const useRenameThread = useRenameThreadMutation;
export const useDeleteThread = useDeleteThreadMutation;

export type TurnState = {
  /** Tokens received so far. Rendered as a provisional assistant bubble. */
  draft: string;
  sources: RetrievedChunk[];
  isStreaming: boolean;
  error: string | null;
  /**
   * The 409 gets its own flag rather than being read back out of the message,
   * because it is not a failure: the project's lore is re-embedding and the turn
   * is worth retrying in a moment. Retrieval is awaited BEFORE the response
   * starts, so this arrives as a clean status code rather than a broken stream.
   */
  isReindexing: boolean;
  /**
   * The thread the meta frame named. On a new conversation this is the FIRST
   * thing the stream reports, before any token, which is what lets the screen
   * select the thread while the reply is still arriving rather than after it.
   */
  threadId: string | null;
};

const EMPTY: TurnState = {
  draft: "",
  sources: [],
  isStreaming: false,
  error: null,
  isReindexing: false,
  threadId: null,
};

/**
 * One streamed turn.
 *
 * This is NOT a useMutation. A mutation models one request with one result; a
 * turn produces a running string that the UI must render as it arrives, and
 * TanStack has nowhere to put that. The durable record is written server-side
 * and read back through the message query -- so the draft is provisional UI
 * state and the transcript stays the single source of truth. That is what makes
 * a reload mid-conversation show the real history rather than a locally
 * accumulated one.
 *
 * The handoff between the two is `transcript.ts`, not a timer: the write is
 * deferred and lands 1.3-1.7 s after `[DONE]`, so the draft is held until the
 * identical row appears and the message query chases it until then.
 */
export const useChatTurn = (projectId: string) => {
  const queryClient = useQueryClient();
  const [state, setState] = useState<TurnState>(EMPTY);

  const send = useCallback(
    async (message: string, threadId: string | null): Promise<void> => {
      // The thread id survives the reset. Blanking it would unmount the message
      // query for a beat and flash the transcript away between turns.
      setState((s) => ({ ...EMPTY, threadId: threadId ?? s.threadId, isStreaming: true }));
      let landedThreadId = threadId;
      try {
        await streamChat({ message, projectId, threadId: threadId ?? undefined }, (event) => {
          if (event.kind === "meta") {
            landedThreadId = event.threadId;
            setState((s) => ({ ...s, sources: event.sources, threadId: event.threadId }));
          } else if (event.kind === "token") {
            setState((s) => ({ ...s, draft: s.draft + event.text }));
          } else {
            setState((s) => ({ ...s, error: event.message }));
          }
        });
      } catch (error) {
        setState((s) => ({
          ...s,
          error: error instanceof ApiError ? error.detail : "The turn failed.",
          isReindexing: error instanceof ReindexInProgressError,
        }));
      } finally {
        setState((s) => ({ ...s, isStreaming: false }));
        // Whatever tokens arrived ARE persisted, even on a failed stream, so the
        // transcript is refetched in every case -- including the error one. This
        // is the optimistic first ask; `useMessagesQuery` keeps asking until the
        // deferred write actually lands.
        queryClient.invalidateQueries({ queryKey: threadKeys.all(projectId) });
        if (landedThreadId) {
          queryClient.invalidateQueries({ queryKey: threadKeys.messages(landedThreadId) });
        }
      }
    },
    [projectId, queryClient],
  );

  const reset = useCallback(() => setState(EMPTY), []);

  return { ...state, send, reset };
};
