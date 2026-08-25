import { createRootRoute, Link, Outlet } from "@tanstack/react-router";

import { ErrorState } from "@/components/ui/ErrorState";

export const Route = createRootRoute({
  component: () => <Outlet />,
  // Without these, a render-time exception leaves a white page and an unroutable
  // URL leaves nothing at all. TanStack Router will call them for anything the
  // route tree throws, including a loader.
  errorComponent: ({ error }) => <ErrorState error={error} size="page" />,
  notFoundComponent: () => (
    <div className="mx-auto max-w-md space-y-2 p-8 text-center">
      <h1 className="text-lg font-semibold">Page not found</h1>
      <p className="text-sm text-muted-foreground">That URL doesn&apos;t exist in the console.</p>
      <Link to="/app" className="text-sm underline underline-offset-4">
        Back to your projects
      </Link>
    </div>
  ),
});
