import { createFileRoute, Navigate } from "@tanstack/react-router";

import { ProjectsEmptyState, useProjects } from "@/features/projects";

/**
 * /app is a junction, not a page.
 *
 * It used to render "Pick a project from the sidebar, or create another one."
 * -- a screen whose entire content was an instruction to leave it. With
 * projects, it now goes to one; without, it is the first-run invitation.
 *
 * The design spec's route map says "last project" here. This sends you to the
 * FIRST, which on a `updated_at`-ordered list is very often the same one, and
 * costs no persisted state. Remembering the actual last one needs storage the
 * spec did not ask for; if it is wanted, that is the change to make.
 */
function AppHome() {
  const { data: projects, isPending } = useProjects();

  if (isPending) return null;
  if (!projects?.length) return <ProjectsEmptyState />;
  return <Navigate to="/app/p/$pid" params={{ pid: projects[0].id }} replace />;
}

export const Route = createFileRoute("/app/")({ component: AppHome });
