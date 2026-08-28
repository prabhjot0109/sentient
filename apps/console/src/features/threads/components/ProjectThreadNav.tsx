import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import type { Thread } from "@/types/threads";

import { useDeleteThread, useRenameThread, useThreads } from "../hooks";
import { DeleteThreadDialog } from "./DeleteThreadDialog";
import { RenameThreadDialog } from "./RenameThreadDialog";
import { ThreadRow } from "./ThreadRow";

/**
 * ui.png's "Show more" threshold. Five rows is roughly what fits under a project
 * before the rail stops being scannable and becomes a list you read.
 */
const COLLAPSED = 5;

/**
 * The conversations belonging to one project, nested under it in the rail.
 *
 * The design spec calls this shape out by name and says to keep it literal:
 * "project rows with nested chat entries and a Show more affordance -- maps
 * directly onto `projects` -> `chat_threads`."
 *
 * Rendered only for the open project, so exactly one threads query is ever in
 * flight regardless of how many projects the rail lists.
 */
export function ProjectThreadNav({
  projectId,
  activeThreadId,
}: {
  projectId: string;
  activeThreadId?: string;
}) {
  const { data: threads = [] } = useThreads(projectId);
  const [expanded, setExpanded] = useState(false);
  const [renaming, setRenaming] = useState<Thread | null>(null);
  const [deleting, setDeleting] = useState<Thread | null>(null);

  const navigate = useNavigate();
  const rename = useRenameThread(projectId);
  const remove = useDeleteThread(projectId);

  const head = expanded ? threads : threads.slice(0, COLLAPSED);
  // Server order is `updated_at DESC`, so a conversation the user is reading can
  // sit past the fold as soon as another one is touched. Collapsing it out of
  // sight would hide the row the rail is currently highlighting, so it is
  // appended rather than dropped.
  const strandedActive =
    activeThreadId && !head.some((t) => t.id === activeThreadId)
      ? threads.find((t) => t.id === activeThreadId)
      : undefined;

  const visible = strandedActive ? [...head, strandedActive] : head;

  if (threads.length === 0) return null;

  return (
    // The hairline is the nesting: it ties every conversation to the project row
    // above it without indenting far enough to lose title width in a 256px rail.
    <div className="mt-0.5 ml-4 border-l border-border pl-1">
      <ul className="flex flex-col gap-0.5">
        {visible.map((thread) => (
          <ThreadRow
            key={thread.id}
            thread={thread}
            projectId={projectId}
            isActive={thread.id === activeThreadId}
            onRename={setRenaming}
            onDelete={setDeleting}
          />
        ))}
      </ul>

      {threads.length > COLLAPSED && (
        <button
          type="button"
          onClick={() => setExpanded((open) => !open)}
          className="mt-0.5 rounded-md px-3 py-1 text-xs text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          {expanded ? "Show less" : `Show ${threads.length - COLLAPSED} more`}
        </button>
      )}

      <RenameThreadDialog
        thread={renaming}
        isPending={rename.isPending}
        onClose={() => setRenaming(null)}
        onConfirm={(title) =>
          rename.mutate({ id: renaming!.id, title }, { onSuccess: () => setRenaming(null) })
        }
      />
      <DeleteThreadDialog
        thread={deleting}
        isPending={remove.isPending}
        onClose={() => setDeleting(null)}
        onConfirm={() =>
          remove.mutate(deleting!.id, {
            onSuccess: () => {
              // Only when the deleted conversation is the one on screen. Its
              // route would otherwise stay mounted and refetch a 404.
              if (deleting!.id === activeThreadId) {
                void navigate({ to: "/app/p/$pid", params: { pid: projectId } });
              }
              setDeleting(null);
            },
          })
        }
      />
    </div>
  );
}
