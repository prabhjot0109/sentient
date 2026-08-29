import type { RetrievedChunk } from "@/types/threads";

import { apiStream } from "./client";
import { parseSseFrames } from "./sse";

/**
 * What a caller needs from a streamed turn. A discriminated union rather than
 * three callbacks, so a consumer that forgets a case fails to typecheck.
 */
export type ChatStreamEvent =
  | {
      kind: "meta";
      threadId: string;
      sources: RetrievedChunk[];
      /**
       * Set when the lore lookup FAILED, which an empty `sources` alone cannot
       * say. The reply then came from the persona with no lore behind it, and
       * the transcript has to admit that rather than render nothing.
       */
      retrievalError: string | null;
      /**
       * The lookup ran, matched nothing, and this project's documents were
       * embedded under a different signature than the one queried. Not "no lore":
       * lore this deployment can no longer reach. Only a reindex fixes it.
       */
      staleIndex: boolean;
      topK: number | null;
    }
  | { kind: "token"; text: string }
  | { kind: "error"; message: string };

export type ChatStreamInput = {
  message: string;
  projectId: string;
  threadId?: string;
};

/**
 * Reads `POST /v1/chat` with `{"stream": true}`.
 *
 * The frame contract (README § "Streaming on POST /v1/chat"):
 *   1. one `sentient.chat.meta` frame -- the ChatResponse fields that cannot be
 *      appended after the stream, because the client renders as it reads,
 *   2. then OpenAI `chat.completion.chunk` frames,
 *   3. then `[DONE]`.
 *
 * Two rules that are easy to get backwards:
 *
 * - **Check for a top-level `error` key FIRST**, before dispatching on `object`.
 *   A provider that dies mid-stream reports in-band as the last frame before
 *   [DONE], because HTTP 200 was already committed when the first frame flushed.
 *   Filtering on `object` first drops it and the turn just stops, which is
 *   exactly the silence the in-band error exists to end.
 * - **Then skip anything that is not a `chat.completion.chunk`.** That is what
 *   makes future metadata frames free to add.
 *
 * `stream` requires `project_id`; without it the backend answers 400. The
 * projectless path has no streaming twin and a fake single-chunk stream would
 * hide that.
 */
export async function streamChat(
  input: ChatStreamInput,
  onEvent: (event: ChatStreamEvent) => void,
): Promise<void> {
  const response = await apiStream("/v1/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      message: input.message,
      project_id: input.projectId,
      thread_id: input.threadId,
      stream: true,
    }),
  });

  if (!response.body) throw new Error("The server sent no stream to read.");

  for await (const payload of parseSseFrames(response.body)) {
    if (payload === "[DONE]") return;

    let frame: Record<string, unknown>;
    try {
      frame = JSON.parse(payload);
    } catch {
      // A malformed frame is not worth killing a turn that is otherwise arriving.
      continue;
    }

    if (frame.error) {
      const error = frame.error as { message?: string };
      onEvent({ kind: "error", message: error.message ?? "The provider failed." });
      return;
    }

    if (frame.object === "sentient.chat.meta") {
      onEvent({
        kind: "meta",
        threadId: frame.thread_id as string,
        sources: (frame.sources ?? []) as RetrievedChunk[],
        retrievalError: (frame.retrieval_error ?? null) as string | null,
        staleIndex: (frame.stale_index ?? false) as boolean,
        topK: (frame.top_k ?? null) as number | null,
      });
      continue;
    }

    if (frame.object !== "chat.completion.chunk") continue;

    // The first chunk carries `delta: {"role": "assistant"}` and no content --
    // measured, not assumed. Guarding on the text rather than on the index is
    // what makes that frame a no-op instead of an "undefined" in the bubble.
    const choices = frame.choices as { delta?: { content?: string } }[] | undefined;
    const text = choices?.[0]?.delta?.content;
    if (text) onEvent({ kind: "token", text });
  }
}
