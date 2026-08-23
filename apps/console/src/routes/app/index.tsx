import { createFileRoute } from "@tanstack/react-router";

import { ProjectsEmptyState, useProjects } from "@/features/projects";

function AppHome() {
  const { data: projects, isPending } = useProjects();

  if (isPending) return null;
  if (!projects?.length) return <ProjectsEmptyState />;
  return (
    <p className="p-8 text-sm text-muted-foreground">
      Pick a project from the sidebar, or create another one.
    </p>
  );
}

export const Route = createFileRoute("/app/")({ component: AppHome });
