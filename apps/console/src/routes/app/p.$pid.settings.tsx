import { createFileRoute } from "@tanstack/react-router";

import { ProjectHeader } from "@/features/projects";
import { SettingsScreen } from "@/features/settings";

function ProjectSettings() {
  const { pid } = Route.useParams();
  return (
    <div className="mx-auto max-w-3xl px-6 py-8 md:px-10">
      <ProjectHeader projectId={pid} />
      <SettingsScreen projectId={pid} />
    </div>
  );
}

export const Route = createFileRoute("/app/p/$pid/settings")({ component: ProjectSettings });
