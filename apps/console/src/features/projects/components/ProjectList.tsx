import { useProjects } from "../hooks";
import { NewProjectDialog } from "./NewProjectDialog";
import { ProjectRow } from "./ProjectRow";
import { ErrorState } from "@/components/ui/ErrorState";

/** The rail. The feature's top-level component, and the only one that fetches. */
export function ProjectList({ activeProjectId }: { activeProjectId?: string }) {
  const { data: projects, isPending, error } = useProjects();

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between px-2">
        <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Projects
        </span>
        <NewProjectDialog
          label="+ New"
          variant="ghost"
          size="sm"
          className="h-auto px-1.5 py-0.5 text-xs text-muted-foreground"
        />
      </div>

      {isPending && <p className="px-2 text-sm text-muted-foreground">Loading projects…</p>}
      {error && <ErrorState error={error} />}
      {projects?.length === 0 && (
        <p className="px-2 text-sm text-muted-foreground">No projects yet.</p>
      )}

      <nav className="flex flex-col gap-0.5">
        {projects?.map((project) => (
          <ProjectRow
            key={project.id}
            project={project}
            isActive={project.id === activeProjectId}
          />
        ))}
      </nav>
    </div>
  );
}
