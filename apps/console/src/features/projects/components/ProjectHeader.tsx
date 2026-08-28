import { Link, useRouterState } from "@tanstack/react-router";

import { useProject } from "../hooks";

/**
 * The header every project sub-page shares: the project's name, and the three
 * places you can be inside it.
 *
 * Before this, each sub-page hand-rolled a "← Back to project" link and its own
 * <h1>, so moving between a project's lore and its settings meant going up and
 * back down. Three tabs is the same three destinations with none of that, and it
 * is the first thing that tells you a project HAS three faces.
 */
export function ProjectHeader({ projectId }: { projectId: string }) {
  const { data: project } = useProject(projectId);
  const pathname = useRouterState({ select: (state) => state.location.pathname });

  /*
   * Derived rather than left to `activeProps`, because neither of that prop's
   * two modes is right here. Exact matching leaves every tab dark while you are
   * reading a conversation at /t/$tid; prefix matching lights "Conversation" on
   * the lore and settings pages too, since its path is a prefix of both.
   */
  const base = `/app/p/${projectId}`;
  const tabs = [
    {
      to: "/app/p/$pid",
      label: "Conversation",
      active: pathname === base || pathname.startsWith(`${base}/t/`),
    },
    { to: "/app/p/$pid/documents", label: "Lore", active: pathname === `${base}/documents` },
    { to: "/app/p/$pid/settings", label: "Settings", active: pathname === `${base}/settings` },
  ] as const;

  return (
    <header className="mb-8">
      {/*
        Display face at a size the 256px rail cannot reach. The project name is
        the one proper noun on the page -- it is the game -- so it gets the only
        large type here.
      */}
      <h1 className="font-display truncate text-2xl font-semibold tracking-tight">
        {project?.name ?? " "}
      </h1>

      <nav className="-mx-3 mt-4 flex gap-1 border-b border-border">
        {tabs.map((tab) => (
          <Link
            key={tab.to}
            to={tab.to}
            params={{ pid: projectId }}
            aria-current={tab.active ? "page" : undefined}
            className={`-mb-px border-b-2 px-3 pb-2 text-sm transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${
              tab.active
                ? "border-foreground text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
