import { Button } from "@/components/ui/Button";
import type { Thread } from "@/types/threads";

import { ThreadRow } from "./ThreadRow";

/**
 * Server order is `updated_at DESC, id DESC` on BOTH stores -- most recent
 * first, which is the order this wants. Do not sort here: a second sort on a
 * nullable timestamp is how the order silently becomes non-deterministic.
 */
export function ThreadList({
  threads,
  activeId,
  onSelect,
  onRename,
  onDelete,
  onNew,
}: {
  threads: Thread[];
  activeId: string | null;
  onSelect: (thread: Thread) => void;
  onRename: (thread: Thread) => void;
  onDelete: (thread: Thread) => void;
  onNew: () => void;
}) {
  return (
    <div className="w-full shrink-0 space-y-2 border-b border-border pb-3 md:w-64 md:border-r md:border-b-0 md:pr-3 md:pb-0">
      <Button size="sm" onClick={onNew} className="w-full">
        New conversation
      </Button>
      {threads.length === 0 ? (
        <p className="px-2 text-xs text-muted-foreground">
          No conversations yet. Talk to an NPC in-game, or start one here.
        </p>
      ) : (
        <ul className="space-y-0.5">
          {threads.map((thread) => (
            <ThreadRow
              key={thread.id}
              thread={thread}
              isActive={thread.id === activeId}
              onSelect={onSelect}
              onRename={onRename}
              onDelete={onDelete}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
