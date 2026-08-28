import { useNavigate } from "@tanstack/react-router";
import { useEffect, useRef } from "react";

import { PageColumn } from "@/components/shell/PageColumn";

import { useChatTurn, useMessages, useThreads } from "../hooks";
import { showDraft } from "../transcript";
import { Composer } from "./Composer";
import { MessageList } from "./MessageList";
import { SourcesPanel } from "./SourcesPanel";

/**
 * One conversation: the transcript, the turn in flight, and the composer.
 *
 * It no longer owns the thread LIST or the selected id. Selection is navigation
 * and now lives in the URL, which is what let the rail nest a conversation under
 * its project -- see `ProjectThreadNav`.
 *
 * `threadId` is null on the project home, where the composer starts a
 * conversation that does not exist yet.
 */
export function ChatScreen({
  projectId,
  threadId,
}: {
  projectId: string;
  threadId: string | null;
}) {
  const navigate = useNavigate();
  const turn = useChatTurn(projectId);
  const endRef = useRef<HTMLDivElement>(null);

  // A new conversation gets its id from the meta frame, which arrives BEFORE the
  // first token. Deriving the active thread rather than assigning it after the
  // stream is what mounts the transcript query while the reply is still arriving,
  // and what makes the second message continue the SAME thread.
  const activeId = threadId ?? turn.threadId;
  const { data: messages = [] } = useMessages(activeId, turn.draft, turn.isStreaming);

  // Whose voice this transcript is in. Read off the rail's already-cached thread
  // list rather than fetched again -- npc_name is set by the game path and null
  // for a conversation this console started, which is the same discriminator the
  // rail uses to mark an in-game memory.
  const { data: threads = [] } = useThreads(projectId);
  const speaker = threads.find((t) => t.id === activeId)?.npc_name;
  const draftVisible = showDraft(messages, turn.draft, turn.isStreaming);

  /*
   * Give a conversation started here its own URL -- but only once the server has
   * written it down.
   *
   * The two obvious moments are both wrong, and for measured reasons. Navigating
   * on the meta frame unmounts the stream mid-flight. Navigating on `[DONE]`
   * lands 1.3-1.7 s BEFORE the deferred transcript write (measured 2026-08-23,
   * three trials), so the remount would render a transcript missing the reply the
   * user just watched arrive -- the exact bug `transcript.ts` exists to close.
   *
   * So it waits on that same settlement signal. By the time it fires, this
   * thread's messages are already in the query cache under the key the new route
   * will read, so the remount is a cache hit with no flash. `replace` keeps Back
   * pointing at the project home rather than at a home that would now redirect
   * straight back here.
   */
  useEffect(() => {
    if (threadId === null && turn.threadId && !draftVisible) {
      void navigate({
        to: "/app/p/$pid/t/$tid",
        params: { pid: projectId, tid: turn.threadId },
        replace: true,
      });
    }
  }, [threadId, turn.threadId, draftVisible, projectId, navigate]);

  // Follow the reply as it streams. `block: "end"` on a trailing anchor rather
  // than a scrollTop assignment, so it works inside whichever ancestor actually
  // scrolls without this component having to know which one that is.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages.length, turn.draft]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/*
        The transcript and the dock each carry their own PageColumn rather than
        sharing one around both. The dock's backdrop has to span the full width
        of <main> so the transcript dissolves into it edge to edge; only the
        control inside it is column-width.
      */}
      <PageColumn className="flex-1">
        <MessageList
          messages={messages}
          draft={turn.draft}
          showDraft={draftVisible}
          isStreaming={turn.isStreaming}
          speaker={speaker}
        />
        <div ref={endRef} />
      </PageColumn>

      {/*
        Sticky rather than fixed: the composer stays reachable while the
        transcript scrolls under it, without this component having to own the
        page's scroll container.
      */}
      <div className="sticky bottom-0 mt-8">
        {/*
          A fade, not a blur. Blurred text behind a translucent bar is still
          legible enough to read as a rendering fault; a gradient to the page
          colour ends the transcript deliberately. The strip must sit OUTSIDE
          the opaque block, or it would be painted over by it.
        */}
        <div
          aria-hidden
          className="pointer-events-none h-8 bg-gradient-to-b from-transparent to-background"
        />
        <div className="bg-background pb-6">
          <PageColumn className="space-y-3">
            <SourcesPanel sources={turn.sources} />

            {/*
              The 409 is not a failure and must not read as one: retrieval is
              awaited before the response starts, so a reindexing project answers a
              clean status code rather than opening a stream and breaking it.
            */}
            {/*
              Amber, matching ErrorState's `warning` tone rather than --brand:
              --brand is the console's identity colour and is spent on the rail's
              provenance marker. A status message borrowing it would make the two
              mean the same thing.
            */}
            {turn.isReindexing ? (
              <p className="rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-sm">
                This project&rsquo;s lore is re-embedding. NPCs can&rsquo;t cite it until that
                finishes — send again in a moment.
              </p>
            ) : (
              // Already human copy: useChatTurn stores `ApiError.detail`, the
              // backend's own sentence, never `.message` with its HTTP status.
              turn.error && <p className="text-sm text-destructive">{turn.error}</p>
            )}

            <Composer
              onSend={(message) => void turn.send(message, activeId)}
              disabled={turn.isStreaming}
            />
          </PageColumn>
        </div>
      </div>
    </div>
  );
}
