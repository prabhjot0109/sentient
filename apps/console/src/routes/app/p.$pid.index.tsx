import { createFileRoute, Link } from "@tanstack/react-router";

import { DocumentsScreen } from "@/features/documents";
import { useProject } from "@/features/projects";
import { ErrorState } from "@/components/ui/ErrorState";

function ProjectHome() {
  const { pid } = Route.useParams();
  const { data: project, error, isPending } = useProject(pid);

  if (isPending) return <p className="p-8 text-sm text-muted-foreground">Loading…</p>;

  // Both branches collapse here: describe() already distinguishes a 404 from
  // everything else, and its 404 copy is the same sentence this route used to
  // hand-roll.
  if (error) return <ErrorState error={error} size="page" />;

  return (
    <div className="space-y-6 p-8">
      <header className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-xl font-semibold">{project.name}</h1>
          <p className="text-sm text-muted-foreground">
            Preset <code>{project.base_preset}</code> · persona from{" "}
            <strong>{project.persona_source}</strong>
          </p>
        </div>
        <div className="flex shrink-0 gap-4">
          <Link
            to="/app/p/$pid/chat"
            params={{ pid }}
            className="text-sm underline underline-offset-4"
          >
            Conversations →
          </Link>
          <Link
            to="/app/p/$pid/settings"
            params={{ pid }}
            className="text-sm underline underline-offset-4"
          >
            Settings →
          </Link>
        </div>
      </header>

      <section className="space-y-1">
        <h2 className="text-sm font-medium">Persona</h2>
        <p className="max-w-2xl rounded-md border border-border bg-card p-3 text-sm text-muted-foreground">
          {project.persona_prompt || "No persona: NPCs answer without an in-world voice."}
        </p>
      </section>

      <DocumentsScreen projectId={pid} />
    </div>
  );
}

export const Route = createFileRoute("/app/p/$pid/")({ component: ProjectHome });
