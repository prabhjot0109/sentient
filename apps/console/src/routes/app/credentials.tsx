import { createFileRoute } from "@tanstack/react-router";

import { VaultScreen } from "@/features/credentials";

/**
 * `/app/credentials`, NOT `/app/p/$pid/credentials`. `provider_credentials` is
 * UNIQUE(user_id, provider) and has no `project_id`, so nesting it under a
 * project would tell the user these keys belong to that project -- and removing
 * one would silently affect every other project they own.
 */
export const Route = createFileRoute("/app/credentials")({
  component: () => (
    <div className="p-8">
      <VaultScreen />
    </div>
  ),
});
