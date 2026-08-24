import { createFileRoute, Link } from "@tanstack/react-router";

import { SettingsScreen } from "@/features/settings";

function ProjectSettings() {
  const { pid } = Route.useParams();
  return (
    <div className="space-y-6 p-8">
      <header className="space-y-1">
        <Link to="/app/p/$pid" params={{ pid }} className="text-sm text-muted-foreground">
          ← Back to project
        </Link>
        <h1 className="text-xl font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground">
          How NPCs in this project think, and how they sound.
        </p>
      </header>
      <SettingsScreen projectId={pid} />
    </div>
  );
}

export const Route = createFileRoute("/app/p/$pid/settings")({ component: ProjectSettings });
