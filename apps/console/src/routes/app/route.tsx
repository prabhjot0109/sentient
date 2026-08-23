import { createFileRoute, Outlet } from "@tanstack/react-router";

import { RequireSession, useSignOut } from "@/features/auth";

function AppShell() {
  const signOut = useSignOut();
  return (
    <RequireSession>
      <div className="flex min-h-screen">
        {/* F2 replaces this rail with the projects sidebar. */}
        <aside className="w-64 shrink-0 border-r p-4">
          <button className="text-sm underline" onClick={signOut}>
            Sign out
          </button>
        </aside>
        <main className="flex-1">
          <Outlet />
        </main>
      </div>
    </RequireSession>
  );
}

export const Route = createFileRoute("/app")({ component: AppShell });
