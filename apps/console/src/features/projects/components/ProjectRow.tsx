import { Link, useNavigate } from "@tanstack/react-router";
import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";

import { ProjectThreadNav } from "@/features/threads";
import { REINDEXING, type Project } from "@/types/projects";

import { DeleteProjectDialog } from "./DeleteProjectDialog";
import { RenameProjectDialog } from "./RenameProjectDialog";

/**
 * A project in the rail, and -- when it is the open one -- its conversations
 * nested underneath.
 *
 * Rename and delete are two always-rendered icon buttons rather than an overflow
 * menu. A correct menu is a focus trap plus outside-click plus Escape plus roving
 * tabindex; two buttons reach the same two actions with none of it.
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
        className={`group flex items-center gap-1 rounded-md px-2 py-1.5 transition-colors ${
          isActive ? "bg-sidebar-accent" : "hover:bg-sidebar-accent/50"
        }`}
      >
        <Link
          to="/app/p/$pid"
          params={{ pid: project.id }}
          className="min-w-0 flex-1 text-sm font-medium text-sidebar-foreground"
        >
          <span className="block truncate">{project.name}</span>
          {project.status === REINDEXING && (
            // Surfaced in the rail rather than left for the user to discover as a
            // 409 mid-conversation: retrieval and chat both refuse while it holds.
            <span className="text-xs font-normal text-muted-foreground">
              re-embedding your lore…
            </span>
          )}
        </Link>

        <button
          type="button"
          aria-label={`Rename ${project.name}`}
          onClick={() => setDialog("rename")}
          className="rounded p-1 opacity-0 group-focus-within:opacity-60 group-hover:opacity-60 hover:!opacity-100"
        >
          <Pencil className="size-3.5" />
        </button>
        <button
          type="button"
          aria-label={`Delete ${project.name}`}
          onClick={() => setDialog("delete")}
          className="rounded p-1 opacity-0 group-focus-within:opacity-60 group-hover:opacity-60 hover:!opacity-100"
        >
          <Trash2 className="size-3.5" />
        </button>
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
          if (isActive) navigate({ to: "/app" });
        }}
      />
    </div>
  );
}
