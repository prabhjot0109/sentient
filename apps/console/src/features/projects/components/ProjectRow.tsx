import { Link, useNavigate } from "@tanstack/react-router";
import { FileText, Pencil, SlidersHorizontal, Trash2 } from "lucide-react";
import { useState } from "react";

import { Menu } from "@/components/ui/Menu";
import { ProjectThreadNav } from "@/features/threads";
import { REINDEXING, type Project } from "@/types/projects";

import { DeleteProjectDialog } from "./DeleteProjectDialog";
import { RenameProjectDialog } from "./RenameProjectDialog";

/**
 * A project in the rail, and -- when it is the open one -- its conversations
 * nested underneath.
 *
 * WHY THIS IS A MENU NOW. It used to be two always-rendered icon buttons, on the
 * reasoning that two buttons beat a menu because a correct menu is a focus trap
 * plus outside-click plus Escape plus roving tabindex. That reasoning was sound
 * and the conclusion was still wrong, because of what the two buttons cost to
 * avoid it: they were 22px targets held at `opacity-0` until the row was
 * hovered, crammed against the right edge of a 256px rail, and they were the
 * ONLY route to rename or delete anywhere in the console. Measured in a headless
 * browser, the click handler fired and the dialog opened correctly every time --
 * the control worked and could not be found, which reaches the user as "the
 * buttons don't work".
 *
 * The machinery that argument was avoiding is free now: `Menu` is built on the
 * native Popover API, which gives light-dismiss, Escape and top-layer stacking
 * from the platform. So the trade the original comment priced no longer exists,
 * and what is left is one 32px control that is visible at rest.
 *
 * It is also no longer the only route. The same four actions are on the project
 * header and in the command palette, so a user who never opens this menu can
 * still reach them.
 */
export function ProjectRow({
  project,
  isActive,
  activeThreadId,
}: {
  project: Project;
  isActive: boolean;
  activeThreadId?: string;
}) {
  const [dialog, setDialog] = useState<"none" | "rename" | "delete">("none");
  const navigate = useNavigate();

  return (
    <div>
      <div
        className={`group flex items-center gap-1 rounded-md pr-1 pl-2 transition-colors duration-[--duration-instant] ${
          isActive ? "bg-sidebar-accent" : "hover:bg-sidebar-accent/50"
        }`}
      >
        <Link
          to="/app/p/$pid"
          params={{ pid: project.id }}
          className="min-w-0 flex-1 rounded-md py-1.5 text-sm font-medium text-sidebar-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <span className="block truncate">{project.name}</span>
          {project.status === REINDEXING && (
            // Surfaced in the rail rather than left for the user to discover as a
            // 409 mid-conversation: retrieval and chat both refuse while it holds.
            <span className="flex items-center gap-1.5 text-xs font-normal text-warning">
              <span
                aria-hidden
                className="size-1.5 shrink-0 rounded-full bg-warning motion-safe:animate-pulse"
              />
              re-embedding your lore…
            </span>
          )}
        </Link>

        {/*
          `opacity-60` at rest, not `opacity-0`. The control is legible without
          hovering -- which is the entire fix -- and hover still promotes it, so
          the rail does not read as a column of identical dots. Touch devices have
          no hover at all and get the resting state, which is now a usable one.
        */}
        <Menu
          label={`Actions for ${project.name}`}
          className="opacity-60 group-focus-within:opacity-100 group-hover:opacity-100"
          items={[
            { label: "Rename", icon: Pencil, onSelect: () => setDialog("rename") },
            {
              label: "Lore",
              icon: FileText,
              onSelect: () =>
                void navigate({ to: "/app/p/$pid/documents", params: { pid: project.id } }),
            },
            {
              label: "Settings",
              icon: SlidersHorizontal,
              onSelect: () =>
                void navigate({ to: "/app/p/$pid/settings", params: { pid: project.id } }),
            },
            { label: "Delete", icon: Trash2, danger: true, onSelect: () => setDialog("delete") },
          ]}
        />
      </div>

      {/*
        Only the open project unfurls, so exactly one threads query is in flight
        no matter how many projects the rail lists -- and the rail stays short
        enough to scan, which is the whole reason ui.png nests rather than
        listing every conversation flat.
      */}
      {isActive && <ProjectThreadNav projectId={project.id} activeThreadId={activeThreadId} />}

      <RenameProjectDialog
        project={project}
        open={dialog === "rename"}
        onClose={() => setDialog("none")}
      />
      <DeleteProjectDialog
        project={project}
        open={dialog === "delete"}
        onClose={() => setDialog("none")}
        // Only when the deleted project is the one on screen. Navigating away from
        // a project the user is not looking at would yank them out of their work.
        onDeleted={() => {
          if (isActive) void navigate({ to: "/app" });
        }}
      />
    </div>
  );
}
