import { Link } from "@tanstack/react-router";
import { Pencil, Trash2 } from "lucide-react";

import { Menu } from "@/components/ui/Menu";
import { absoluteTime, relativeTime } from "@/lib/time";
import type { Thread } from "@/types/threads";

/**
 * One conversation in the rail.
 *
 * A `<Link>`, not a button with a callback, and that is the whole point of the
 * change: while the selected thread lived in `ChatScreen`'s `useState` nothing
 * outside that component could address a conversation, so the rail could not
 * nest one under its project no matter how it was drawn.
 *
 * The two actions used to be text buttons in an absolutely-positioned strip laid
 * OVER the title, with `pr-14` on the link reserving room for them and
 * `max-md:flex` pinning them open on touch -- so on a phone every row
 * permanently spent 56px of a 256px rail on two controls sitting on top of the
 * name they act on. They are a menu now, in the flow, one 28px control wide, and
 * the title gets the space back.
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
  const when = relativeTime(thread.updated_at);

  return (
    <li
      className={`group flex items-center gap-0.5 rounded-md pr-0.5 transition-colors duration-[--duration-instant] ${
        isActive ? "bg-muted" : "hover:bg-muted/60"
      }`}
    >
      <Link
        to="/app/p/$pid/t/$tid"
        params={{ pid: projectId, tid: thread.id }}
        title={label}
        className={`min-w-0 flex-1 rounded-md py-1.5 pl-3 text-sm transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${
          isActive ? "text-foreground" : "text-muted-foreground group-hover:text-foreground"
        }`}
      >
        <span className="flex items-center gap-2">
          {/*
            The one place --brand is spent in the rail. An in-game conversation is
            a memory Skyrim wrote into the same table this console writes to, and
            nothing else in the product shows that at a glance.
          */}
          {inGame && (
            <span
              aria-hidden
              title="Held in game"
              className="size-1.5 shrink-0 rounded-full bg-brand"
            />
          )}
          <span className="min-w-0 flex-1 truncate">{label}</span>
        </span>
        {/*
          The timestamp is what makes an ordered list readable as one: the server
          returns `updated_at DESC` and until now the rail showed the order
          without ever showing the reason for it. `time` with a machine-readable
          datetime, so the value is not merely a rendered string.
        */}
        {when && (
          <time
            dateTime={thread.updated_at}
            title={absoluteTime(thread.updated_at)}
            className="mt-0.5 block truncate pl-0.5 text-[11px] text-muted-foreground"
          >
            {when}
          </time>
        )}
      </Link>

      <Menu
        label={`Actions for ${label}`}
        className="size-7 opacity-60 group-focus-within:opacity-100 group-hover:opacity-100"
        items={[
          { label: "Rename", icon: Pencil, onSelect: () => onRename(thread) },
          { label: "Delete", icon: Trash2, danger: true, onSelect: () => onDelete(thread) },
        ]}
      />
    </li>
  );
}
