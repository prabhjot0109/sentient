import { useMutation, useQuery } from "@tanstack/react-query";

import { recentTranscriptions, transcribe } from "@/lib/api/audio";

export const voiceKeys = {
  recent: () => ["voice", "recent"] as const,
};

/**
 * Not cached and not keyed. Every utterance is a distinct one-shot write whose
 * result is consumed immediately by the composer, so there is nothing for a
 * query cache to hold and nothing for it to invalidate.
 */
export const useTranscribeMutation = () =>
  useMutation({ mutationFn: (audio: Blob) => transcribe(audio) });

/**
 * The mic diagnostics buffer.
 *
 * Deliberately NO `refetchInterval`. The utterances this panel exists to explain
 * arrive while the reader is in Skyrim, not looking at a browser tab, so a timer
 * would spend requests on nobody. TanStack refetches on window focus by default
 * and `main.tsx` builds a bare QueryClient, so alt-tabbing back -- the actual
 * moment of use -- already produces fresh data.
 *
 * `staleTime: 0` makes that focus refetch unconditional rather than
 * subject to a freshness window that would swallow it.
 */
export const useRecentUtterancesQuery = () =>
  useQuery({
    queryKey: voiceKeys.recent(),
    queryFn: () => recentTranscriptions(),
    staleTime: 0,
  });
