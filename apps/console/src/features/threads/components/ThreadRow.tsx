import { Link } from "@tanstack/react-router";

import type { Thread } from "@/types/threads";

/**
 * One conversation in the rail.
 *
 * A `<Link>`, not a button with a callback, and that is the whole point of the
 * change: while the selected thread lived in `ChatScreen`'s `useState` nothing
 * outside that component could address a conversation, so the rail could not
 * nest one under its project no matter how it was drawn.
 */
export function ThreadRow({
  thread,
  projectId,
  isActive,
  onRename,
  onDelete,
}: {
  thread: Thread;
  projectId: string;
  isActive: boolean;
  onRename: (thread: Thread) => void;
  onDelete: (thread: Thread) => void;
}) {
  // npc_name is the discriminator between a thread Mantella wrote in Skyrim and
  // one this console created (G4: both surfaces share chat_threads). It is also
  // the only label a game thread has -- its title is null, measured 2026-08-23 --
  // so without it the rail reads as a pile of untitled conversations.
  const inGame = thread.npc_name !== null;
  const label = thread.title || thread.npc_name || "Untitled conversation";

  return (
    <li className="group relative flex items-center">
      <Link
        to="/app/p/$pid/t/$tid"
        params={{ pid: projectId, tid: thread.id }}
        className={`min-w-0 flex-1 truncate rounded-md py-1.5 pr-14 pl-3 text-sm transition-colors ${
          isActive
            ? "bg-muted text-foreground"
            : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
        }`}
      >
        {/*
          The one place --brand is spent in the rail. An in-game conversation is
          a memory Skyrim wrote into the same table this console writes to, and
          nothing else in the product shows that at a glance.
        */}
        {inGame && (
          <span
            aria-hidden
            className="mr-2 inline-block size-1.5 shrink-0 rounded-full align-middle bg-brand"
          />
        )}
        {label}
      </Link>

      <span className="absolute right-1 hidden items-center gap-0.5 group-focus-within:flex group-hover:flex">
        <button
          type="button"
          aria-label={`Rename ${label}`}
          onClick={() => onRename(thread)}
          className="rounded px-1.5 py-0.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          Rename
        </button>
        <button
          type="button"
          aria-label={`Delete ${label}`}
          onClick={() => onDelete(thread)}
          className="rounded px-1.5 py-0.5 text-xs text-muted-foreground hover:bg-muted hover:text-destructive focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          Delete
        </button>
      </span>
    </li>
  );
}
