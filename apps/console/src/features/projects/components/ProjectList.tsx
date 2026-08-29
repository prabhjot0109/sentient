import { Search } from "lucide-react";
import { useMemo, useState } from "react";

import { ErrorState } from "@/components/ui/ErrorState";
import { SkeletonRows } from "@/components/ui/Skeleton";

import { useProjects } from "../hooks";
import { NewProjectDialog } from "./NewProjectDialog";
import { ProjectRow } from "./ProjectRow";

/**
 * Past this many projects the rail stops being a list you scan and becomes one
 * you search. Below it the filter would be a permanently empty control taking a
 * row of a 260px rail.
 */
const FILTER_THRESHOLD = 6;

/** The rail. The feature's top-level component, and the only one that fetches. */
export function ProjectList({
  activeProjectId,
  activeThreadId,
}: {
  activeProjectId?: string;
  activeThreadId?: string;
}) {
  const { data: projects, isPending, error } = useProjects();
  const [filter, setFilter] = useState("");

  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle || !projects) return projects;
    return projects.filter((project) => project.name.toLowerCase().includes(needle));
  }, [filter, projects]);

  const showFilter = (projects?.length ?? 0) >= FILTER_THRESHOLD;

  return (
    <div className="mt-4 space-y-2 border-t border-sidebar-border pt-4">
      <div className="flex items-center justify-between gap-2 px-2">
        <span className="font-mono text-[11px] tracking-[0.12em] text-muted-foreground uppercase">
          Projects
          {projects && projects.length > 0 && (
            <span className="ml-1.5 text-border">{projects.length}</span>
          )}
        </span>
        <NewProjectDialog
          label="New"
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
        />
      </div>

      {showFilter && (
        <div className="relative px-1">
          <Search
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-muted-foreground"
          />
          <input
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Filter"
            aria-label="Filter projects"
            className="h-8 w-full rounded-md border border-sidebar-border bg-background/40 pr-2 pl-8 text-sm placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          />
        </div>
      )}

      {/*
        A skeleton at the shape of the rows it precedes, not the sentence
        "Loading projects…". The sentence moved the layout twice -- once when it
        appeared and once when the rows pushed it out -- and it was one of four
        different loading sentences across the console for one state.
      */}
      {isPending && <SkeletonRows rows={3} className="h-8" />}
      {error && (
        <div className="px-1">
          <ErrorState error={error} />
        </div>
      )}

      {projects?.length === 0 && (
        <p className="px-2 py-1 text-sm text-muted-foreground">
          No projects yet. A project is one game.
        </p>
      )}

      {visible?.length === 0 && projects && projects.length > 0 && (
        <p className="px-2 py-1 text-sm text-muted-foreground">No project matches that.</p>
      )}

      <nav aria-label="Projects" className="flex flex-col gap-0.5">
        {visible?.map((project) => (
          <ProjectRow
            key={project.id}
            project={project}
            isActive={project.id === activeProjectId}
            activeThreadId={activeThreadId}
          />
        ))}
      </nav>
    </div>
  );
}
