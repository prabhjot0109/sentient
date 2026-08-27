import type { Thread } from "@/types/threads";

export function ThreadRow({
  thread,
  isActive,
  onSelect,
  onRename,
  onDelete,
}: {
  thread: Thread;
  isActive: boolean;
  onSelect: (thread: Thread) => void;
  onRename: (thread: Thread) => void;
  onDelete: (thread: Thread) => void;
}) {
  return (
    <li className={`group rounded-md px-2 py-1.5 ${isActive ? "bg-muted" : "hover:bg-muted/50"}`}>
      <button
        type="button"
        onClick={() => onSelect(thread)}
        className="block w-full truncate text-left text-sm"
      >
        {thread.title || "Untitled conversation"}
      </button>
      <div className="flex items-center justify-between">
        {/*
          npc_name is the discriminator between a thread Mantella wrote in Skyrim
          and one this console created (G4: both surfaces share chat_threads).
          Without this badge the sidebar reads as a pile of untitled chats -- a
          game thread has no title at all, measured 2026-08-23.
        */}
        {thread.npc_name ? (
          <span className="truncate text-xs text-muted-foreground">
            in-game · {thread.npc_name}
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">console</span>
        )}
        <span className="hidden shrink-0 gap-2 group-hover:flex">
          <button
            type="button"
            onClick={() => onRename(thread)}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Rename
          </button>
          <button
            type="button"
            onClick={() => onDelete(thread)}
            className="text-xs text-muted-foreground hover:text-destructive"
          >
            Delete
          </button>
        </span>
      </div>
    </li>
  );
}
