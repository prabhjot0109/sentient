import { createFileRoute, Link } from "@tanstack/react-router";

import { ChatScreen } from "@/features/threads";

function ProjectChat() {
  const { pid } = Route.useParams();
  return (
    <div className="space-y-6 p-8">
      <header className="space-y-1">
        <Link to="/app/p/$pid" params={{ pid }} className="text-sm text-muted-foreground">
          ← Back to project
        </Link>
        <h1 className="text-xl font-semibold">Conversations</h1>
        <p className="text-sm text-muted-foreground">
          Everything this project has said — in this console and in-game.
        </p>
      </header>
      <ChatScreen projectId={pid} />
    </div>
  );
}

export const Route = createFileRoute("/app/p/$pid/chat")({ component: ProjectChat });
