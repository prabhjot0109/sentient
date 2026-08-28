import { createFileRoute, Link, Outlet, useParams, useRouterState } from "@tanstack/react-router";
import { KeyRound, Menu, Vault } from "lucide-react";
import { useEffect, useState } from "react";

import { NavRow } from "@/components/shell/NavRow";
import { Sidebar } from "@/components/shell/Sidebar";
import { ThemeToggle } from "@/components/shell/ThemeToggle";
import { ErrorState } from "@/components/ui/ErrorState";
import { RequireSession, useSession, useSignOut } from "@/features/auth";
import { ProjectList } from "@/features/projects";
import { OfflineBanner } from "@/features/system";

function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false);
  const pathname = useRouterState({ select: (state) => state.location.pathname });

  // Close on navigation, or picking a project on a phone leaves the drawer
  // sitting over the project you just opened.
  useEffect(() => setMenuOpen(false), [pathname]);

  // strict:false because this layout renders above /app, /app/p/$pid and
  // /app/p/$pid/t/$tid, and only some of those have each param.
  const { pid, tid } = useParams({ strict: false });

  return (
    <RequireSession>
      <div className="flex h-screen bg-background text-foreground">
        <Sidebar
          open={menuOpen}
          onClose={() => setMenuOpen(false)}
          header={
            <>
              <Link
                to="/app"
                className="flex items-center gap-2 rounded-md px-2 py-1 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                <span aria-hidden className="size-2 rounded-full bg-brand" />
                <span className="font-display text-[15px] font-semibold tracking-tight">
                  Sentient
                </span>
              </Link>

              <nav className="mt-4 flex flex-col gap-0.5">
                <NavRow to="/app/keys" icon={KeyRound} label="API keys" />
                {/*
                  User-level, not project-level -- `provider_credentials` is keyed
                  on the user -- so it belongs in the shell rather than on a
                  project page.
                */}
                <NavRow to="/app/credentials" icon={Vault} label="Provider keys" />
              </nav>
            </>
          }
          footer={<UserRow />}
        >
          <ProjectList activeProjectId={pid} activeThreadId={tid} />
        </Sidebar>

        {/*
          The shell owns the scroll now, not the page. ChatScreen's composer is
          `sticky bottom-0`, which needs an ancestor that actually scrolls; when
          <main> was the scroller AND the body grew, the composer stuck to a
          viewport edge the transcript had already run past.
        */}
        <main className="flex min-w-0 flex-1 flex-col overflow-y-auto">
          <OfflineBanner />
          <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-border bg-background/85 p-3 backdrop-blur md:hidden">
            <button
              type="button"
              aria-label="Open menu"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen(true)}
              className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              <Menu className="size-5" />
            </button>
            <span className="font-display text-sm font-semibold tracking-tight">Sentient</span>
          </div>
          <Outlet />
        </main>
      </div>
    </RequireSession>
  );
}

/**
 * Who is signed in, and the way out. It shows the identity because a console
 * that holds provider keys and mints API keys is one where "which account am I
 * in" is a question worth being able to answer without leaving the page.
 */
function UserRow() {
  const signOut = useSignOut();
  const { data } = useSession();
  const email = data?.user?.email;

  return (
    <div className="flex items-center gap-2">
      <span
        aria-hidden
        className="grid size-7 shrink-0 place-items-center rounded-full bg-sidebar-accent text-xs font-medium text-sidebar-foreground"
      >
        {(email ?? "?").charAt(0).toUpperCase()}
      </span>
      <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground" title={email}>
        {email ?? "Signed in"}
      </span>
      <ThemeToggle />
      <button
        type="button"
        onClick={signOut}
        className="shrink-0 rounded px-1.5 py-0.5 text-xs text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        Sign out
      </button>
    </div>
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
