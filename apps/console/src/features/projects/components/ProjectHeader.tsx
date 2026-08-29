import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Menu } from "@/components/ui/Menu";
import { Skeleton } from "@/components/ui/Skeleton";
import { REINDEXING } from "@/types/projects";

import { useProject } from "../hooks";
import { DeleteProjectDialog } from "./DeleteProjectDialog";
import { RenameProjectDialog } from "./RenameProjectDialog";

/**
 * The header every project sub-page shares: the project's name, what state it is
 * in, the three places you can be inside it, and the two actions that act on it.
 *
 * Before this, each sub-page hand-rolled a "← Back to project" link and its own
 * <h1>, so moving between a project's lore and its settings meant going up and
 * back down. Three tabs is the same three destinations with none of that, and it
 * is the first thing that tells you a project HAS three faces.
 *
 * Rename and delete are here as well as in the rail. They were reachable from
 * exactly one place -- a 22px zero-opacity icon in a 260px rail -- and a user who
 * did not find that concluded the console could not do it. This is the page you
 * are on when you want to act on a project, so it is where the action belongs;
 * the rail's menu and the command palette are the other two ways in.
 */
export function ProjectHeader({ projectId }: { projectId: string }) {
  const { data: project, isPending } = useProject(projectId);
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const [dialog, setDialog] = useState<"none" | "rename" | "delete">("none");
  const navigate = useNavigate();

  /*
   * Derived rather than left to `activeProps`, because neither of that prop's
   * two modes is right here. Exact matching leaves every tab dark while you are
   * reading a conversation at /t/$tid; prefix matching lights "Conversation" on
   * the lore and settings pages too, since its path is a prefix of both.
   */
  const base = `/app/p/${projectId}`;
  const tabs = [
    {
      to: "/app/p/$pid",
      label: "Conversation",
      active: pathname === base || pathname.startsWith(`${base}/t/`),
    },
    { to: "/app/p/$pid/documents", label: "Lore", active: pathname === `${base}/documents` },
    { to: "/app/p/$pid/settings", label: "Settings", active: pathname === `${base}/settings` },
  ] as const;

  return (
    <header className="mb-8">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {/*
            Display face at a size the rail cannot reach. The project name is the
            one proper noun on the page -- it is the game -- so it gets the only
            large type here.
          */}
          {isPending ? (
            <Skeleton className="h-8 w-56" />
          ) : (
            <h1 className="font-display truncate text-2xl font-semibold tracking-tight">
              {project?.name}
            </h1>
          )}
          {project?.status === REINDEXING && (
            <Badge tone="warning" className="mt-2">
              <span
                aria-hidden
                className="size-1.5 rounded-full bg-warning motion-safe:animate-pulse"
              />
              Re-embedding your lore
            </Badge>
          )}
        </div>

        {project && (
          <Menu
            label={`Actions for ${project.name}`}
            items={[
              { label: "Rename project", icon: Pencil, onSelect: () => setDialog("rename") },
              {
                label: "Delete project",
                icon: Trash2,
                danger: true,
                onSelect: () => setDialog("delete"),
              },
            ]}
          />
        )}
      </div>

      <nav aria-label="Project sections" className="-mx-3 mt-5 flex gap-1 border-b border-border">
        {tabs.map((tab) => (
          <Link
            key={tab.to}
            to={tab.to}
            params={{ pid: projectId }}
            aria-current={tab.active ? "page" : undefined}
            className={`-mb-px border-b-2 px-3 pb-2 text-sm transition-colors duration-[--duration-instant] focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${
              tab.active
                ? "border-foreground text-foreground"
                : "border-transparent text-muted-foreground hover:border-border hover:text-foreground"
            }`}
          >
            {tab.label}
          </Link>
        ))}
      </nav>

      {project && (
        <>
          <RenameProjectDialog
            project={project}
            open={dialog === "rename"}
            onClose={() => setDialog("none")}
          />
          <DeleteProjectDialog
            project={project}
            open={dialog === "delete"}
            onClose={() => setDialog("none")}
            onDeleted={() => void navigate({ to: "/app" })}
          />
        </>
      )}
    </header>
  );
}
