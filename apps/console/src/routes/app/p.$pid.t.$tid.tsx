import { createFileRoute } from "@tanstack/react-router";

import { PageColumn } from "@/components/shell/PageColumn";
import { ProjectHeader } from "@/features/projects";
import { ChatScreen } from "@/features/threads";

/**
 * One conversation, addressable.
 *
 * The spec's route map declared this route (§4.6) and the implementation
 * diverged: the selected thread lived in `ChatScreen`'s `useState`, so a reload
 * dropped you to a blank composer, Back did nothing inside chat, and -- the
 * structural cost -- the rail could not nest a conversation under its project,
 * because there was nothing to link to.
 *
 * No conversation title is rendered here on purpose. The rail highlights the
 * open one and the transcript names the speaker on every line; a third label
 * saying the same thing is the accessory to leave off.
 */
function ThreadRoute() {
  const { pid, tid } = Route.useParams();
  return (
    // min-h-full is what lets the composer dock at the bottom of the viewport
    // on a short transcript: without a full-height page the sticky element has
    // nothing to stick to and rides up under the header.
    <div className="flex min-h-full flex-col">
      <PageColumn className="pt-8">
        <ProjectHeader projectId={pid} />
      </PageColumn>
      {/*
        Keyed on the thread so switching conversations remounts rather than
        carrying the previous turn's draft and retrieved sources into the next
        transcript.
      */}
      <ChatScreen key={tid} projectId={pid} threadId={tid} />
    </div>
  );
}

export const Route = createFileRoute("/app/p/$pid/t/$tid")({ component: ThreadRoute });
