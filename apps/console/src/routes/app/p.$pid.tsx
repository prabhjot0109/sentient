import { createFileRoute } from "@tanstack/react-router";

import { DocumentsScreen } from "@/features/documents";
import { useProject } from "@/features/projects";
import { NotFoundError } from "@/lib/api/errors";

function ProjectHome() {
  const { pid } = Route.useParams();
  const { data: project, error, isPending } = useProject(pid);

  if (isPending) return <p className="p-8 text-sm text-muted-foreground">Loading…</p>;

  if (error instanceof NotFoundError) {
    return (
      <div className="space-y-2 p-8">
        <h1 className="text-lg font-semibold">Project not found</h1>
        <p className="text-sm text-muted-foreground">
          It has been deleted, or it belongs to another account.
        </p>
      </div>
    );
  }
  if (error) return <p className="p-8 text-sm text-destructive">{error.message}</p>;

  return (
    <div className="space-y-6 p-8">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold">{project.name}</h1>
        <p className="text-sm text-muted-foreground">
          Preset <code>{project.base_preset}</code> · persona from{" "}
          <strong>{project.persona_source}</strong>
        </p>
      </header>

      <section className="space-y-1">
        <h2 className="text-sm font-medium">Persona</h2>
        <p className="max-w-2xl rounded-md border border-border bg-card p-3 text-sm text-muted-foreground">
          {project.persona_prompt || "No persona: NPCs answer without an in-world voice."}
        </p>
      </section>

      <DocumentsScreen projectId={pid} />

      <p className="text-sm text-muted-foreground">
        Settings and conversations land here as F3 and F5 ship.
      </p>
    </div>
  );
}

export const Route = createFileRoute("/app/p/$pid")({ component: ProjectHome });
