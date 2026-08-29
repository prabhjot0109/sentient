import { createFileRoute } from "@tanstack/react-router";

import { PageColumn } from "@/components/shell/PageColumn";
import { VaultScreen } from "@/features/credentials";

/**
 * `/app/credentials`, NOT `/app/p/$pid/credentials`. `provider_credentials` is
 * UNIQUE(user_id, provider) and has no `project_id`, so nesting it under a
 * project would tell the user these keys belong to that project -- and removing
 * one would silently affect every other project they own.
 */
export const Route = createFileRoute("/app/credentials")({
  component: () => (
    // PageColumn, like every other page inside /app. Two of the account-level
    // screens used a bare `p-8` instead, so their content started at a different
    // x-position from the project pages and did not share the reading measure.
    <PageColumn className="py-10">
      <VaultScreen />
    </PageColumn>
  ),
});
