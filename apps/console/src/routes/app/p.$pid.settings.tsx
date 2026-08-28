import { createFileRoute } from "@tanstack/react-router";

import { PageColumn } from "@/components/shell/PageColumn";
import { ProjectHeader } from "@/features/projects";
import { SettingsScreen } from "@/features/settings";

function ProjectSettings() {
  const { pid } = Route.useParams();
  return (
    <PageColumn className="py-8">
      <ProjectHeader projectId={pid} />
      <SettingsScreen projectId={pid} />
    </PageColumn>
  );
}

export const Route = createFileRoute("/app/p/$pid/settings")({ component: ProjectSettings });
