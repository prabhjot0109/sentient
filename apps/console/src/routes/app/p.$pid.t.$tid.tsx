import { createFileRoute } from "@tanstack/react-router";

import { ChatScreen } from "@/features/threads";

/**
 * One conversation, addressable.
 *
 * The spec's route map declared this route (§4.6) and the implementation
 * diverged: the selected thread lived in `ChatScreen`'s `useState`, so a reload
 * dropped you to a blank composer, Back did nothing inside chat, and -- the
 * structural cost -- the rail could not nest a conversation under its project,
 * because there was nothing to link to.
 */
function ThreadRoute() {
  const { pid, tid } = Route.useParams();
  // Keyed on the thread so switching conversations remounts rather than carrying
  // the previous turn's draft and sources into the next transcript.
  return <ChatScreen key={tid} projectId={pid} threadId={tid} />;
}

export const Route = createFileRoute("/app/p/$pid/t/$tid")({ component: ThreadRoute });
