import { createFileRoute, Link, Outlet, useParams } from "@tanstack/react-router";

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
            <div className="flex items-center justify-between">
              <div className="flex flex-col gap-1">
                <Link to="/app/keys" className="text-sm text-muted-foreground hover:underline">
                  API keys
                </Link>
                {/*
                  User-level, not project-level -- `provider_credentials` is keyed
                  on the user -- so it belongs in the shell rather than on a
                  project page.
                */}
                <Link
                  to="/app/credentials"
                  className="text-sm text-muted-foreground hover:underline"
                >
                  Provider keys
                </Link>
              </div>
              <button className="text-sm text-muted-foreground hover:underline" onClick={signOut}>
                Sign out
              </button>
            </div>
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
