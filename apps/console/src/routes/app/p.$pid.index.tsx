import { createFileRoute } from "@tanstack/react-router";

import { ErrorState } from "@/components/ui/ErrorState";
import { ProjectHeader, useProject } from "@/features/projects";
import { ChatScreen } from "@/features/threads";

/**
 * "Project home / new chat", which is what the design spec's route map calls
 * this surface. It used to be the document manager; lore has its own route now,
 * the one the map always gave it.
 */
function ProjectHome() {
  const { pid } = Route.useParams();
  const { error, isPending } = useProject(pid);

  if (isPending) return <p className="p-8 text-sm text-muted-foreground">Loading…</p>;

  // describe() already distinguishes a 404 from everything else, and its 404
  // copy is the sentence this route used to hand-roll.
  if (error) return <ErrorState error={error} size="page" />;

  return (
    <div className="mx-auto flex min-h-full max-w-3xl flex-col px-6 py-8 md:px-10">
      <ProjectHeader projectId={pid} />
      <ChatScreen projectId={pid} threadId={null} />
    </div>
  );
}

export const Route = createFileRoute("/app/p/$pid/")({ component: ProjectHome });
