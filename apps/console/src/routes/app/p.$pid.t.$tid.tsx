import { createFileRoute } from "@tanstack/react-router";

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
    <div className="mx-auto flex min-h-full max-w-3xl flex-col px-6 pt-8 md:px-10">
      <ProjectHeader projectId={pid} />
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
