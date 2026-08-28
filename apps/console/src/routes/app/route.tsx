import { createFileRoute, Link, Outlet, useParams, useRouterState } from "@tanstack/react-router";
import { Menu } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";

import { Sidebar } from "@/components/shell/Sidebar";
import { ErrorState } from "@/components/ui/ErrorState";
import { RequireSession, useSignOut } from "@/features/auth";
import { ProjectList } from "@/features/projects";
import { OfflineBanner } from "@/features/system";

function AppShell() {
  const signOut = useSignOut();
  const [menuOpen, setMenuOpen] = useState(false);
  const pathname = useRouterState({ select: (state) => state.location.pathname });

  // Close on navigation, or picking a project on a phone leaves the drawer
  // sitting over the project you just opened.
  useEffect(() => setMenuOpen(false), [pathname]);

  // strict:false because this layout renders above both /app/ and /app/p/$pid,
  // and only one of those has a pid.
  const { pid, tid } = useParams({ strict: false });

  return (
    <RequireSession>
      <div className="flex min-h-screen bg-background text-foreground">
        <Sidebar
          open={menuOpen}
          onClose={() => setMenuOpen(false)}
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
          <ProjectList activeProjectId={pid} activeThreadId={tid} />
        </Sidebar>
        <main className="min-w-0 flex-1 overflow-y-auto">
          <OfflineBanner />
          <div className="flex items-center gap-2 border-b border-border p-3 md:hidden">
            <Button
              size="sm"
              aria-label="Open menu"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen(true)}
            >
              <Menu className="size-4" />
            </Button>
          </div>
          <Outlet />
        </main>
      </div>
    </RequireSession>
  );
}

/**
 * The authenticated area's boundary. An UnauthenticatedError is thrown here
 * rather than returned (see main.tsx), so an expired session unmounts the shell
 * and lands on describe()'s "Your session has expired" with a sign-in action --
 * instead of a card stranded beside a sidebar still listing cached projects.
 *
 * It lives on /app rather than __root because signing out is only a sensible
 * offer inside the signed-in area; the root boundary stays domain-free.
 */
function AppShellError({ error }: { error: unknown }) {
  const signOut = useSignOut();
  return (
    <ErrorState
      error={error}
      size="page"
      action={
        <button className="text-sm underline underline-offset-4" onClick={signOut}>
          Sign in again
        </button>
      }
    />
  );
}

export const Route = createFileRoute("/app")({
  component: AppShell,
  errorComponent: AppShellError,
});
