import { createFileRoute } from "@tanstack/react-router";

import { DocumentsScreen } from "@/features/documents";
import { ProjectHeader } from "@/features/projects";

/**
 * The lore manager, on the route the spec's map gave it (§4.6). It was rendered
 * inside the project home instead, which left the home with no identity of its
 * own -- the spec calls that surface "project home / new chat".
 */
function DocumentsRoute() {
  const { pid } = Route.useParams();
  return (
    <div className="mx-auto max-w-3xl px-6 py-8 md:px-10">
      <ProjectHeader projectId={pid} />
      <DocumentsScreen projectId={pid} />
    </div>
  );
}

export const Route = createFileRoute("/app/p/$pid/documents")({ component: DocumentsRoute });
