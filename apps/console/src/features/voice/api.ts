import { useMutation } from "@tanstack/react-query";

import { transcribe } from "@/lib/api/audio";

/**
 * Not cached and not keyed. Every utterance is a distinct one-shot write whose
 * result is consumed immediately by the composer, so there is nothing for a
 * query cache to hold and nothing for it to invalidate.
 */
export const useTranscribeMutation = () =>
  useMutation({ mutationFn: (audio: Blob) => transcribe(audio) });
