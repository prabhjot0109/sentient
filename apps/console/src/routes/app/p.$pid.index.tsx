import { createFileRoute } from "@tanstack/react-router";

import { PageColumn } from "@/components/shell/PageColumn";
import { ErrorState } from "@/components/ui/ErrorState";
import { ProjectHeader, useProject, VoiceHero } from "@/features/projects";
import { ChatScreen } from "@/features/threads";

/**
 * "Project home / new chat", which is what the design spec's route map calls
 * this surface. It used to be the document manager; lore has its own route now,
 * the one the map always gave it.
 */
function ProjectHome() {
  const { pid } = Route.useParams();
  const { data: project, error, isPending } = useProject(pid);

  if (isPending) return <p className="p-8 text-sm text-muted-foreground">Loading…</p>;

  // describe() already distinguishes a 404 from everything else, and its 404
  // copy is the sentence this route used to hand-roll.
  if (error) return <ErrorState error={error} size="page" />;

  return (
    <div className="flex min-h-full flex-col">
      <PageColumn className="pt-8">
        <ProjectHeader projectId={pid} />
        <VoiceHero project={project} />
      </PageColumn>
      <ChatScreen projectId={pid} threadId={null} />
    </div>
  );
}

export const Route = createFileRoute("/app/p/$pid/")({ component: ProjectHome });
