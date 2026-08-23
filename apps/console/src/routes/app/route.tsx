import { createFileRoute, Outlet, useParams } from "@tanstack/react-router";

import { Sidebar } from "@/components/shell/Sidebar";
import { RequireSession, useSignOut } from "@/features/auth";
import { ProjectList } from "@/features/projects";

function AppShell() {
  const signOut = useSignOut();
  // strict:false because this layout renders above both /app/ and /app/p/$pid,
  // and only one of those has a pid.
  const { pid } = useParams({ strict: false });

  return (
    <RequireSession>
      <div className="flex min-h-screen bg-background text-foreground">
        <Sidebar
          footer={
            <button className="text-sm text-muted-foreground hover:underline" onClick={signOut}>
              Sign out
            </button>
          }
        >
          <ProjectList activeProjectId={pid} />
        </Sidebar>
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </RequireSession>
  );
}

export const Route = createFileRoute("/app")({ component: AppShell });
