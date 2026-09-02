import { createFileRoute, Link, Outlet, useParams, useRouterState } from "@tanstack/react-router";
import { KeyRound, LogOut, Menu as MenuIcon, PanelLeft, Search, Vault } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { NavRow } from "@/components/shell/NavRow";
import { Sidebar } from "@/components/shell/Sidebar";
import { ThemeToggle } from "@/components/shell/ThemeToggle";
import { ErrorState } from "@/components/ui/ErrorState";
import { IconButton } from "@/components/ui/IconButton";
import { Kbd } from "@/components/ui/Kbd";
import { Menu } from "@/components/ui/Menu";
import { ToastProvider } from "@/components/ui/Toast";
import { RequireSession, useSession, useSignOut } from "@/features/auth";
import { CommandPalette, PALETTE_HINT } from "@/features/command";
import { ProjectList } from "@/features/projects";
import { OfflineBanner } from "@/features/system";
import { useHotkey } from "@/lib/hotkeys";
import { usePersistedBoolean } from "@/lib/persisted";
import { ISSUES_URL, PRIVACY_URL, TERMS_URL } from "@/lib/site";

function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [railHidden, setRailHidden] = usePersistedBoolean("sentient.rail.hidden", false);
  const pathname = useRouterState({ select: (state) => state.location.pathname });

  // Close on navigation, or picking a project on a phone leaves the drawer
  // sitting over the project you just opened.
  useEffect(() => setMenuOpen(false), [pathname]);

  // `whileTyping` on the palette only. It is the one binding a text field cannot
  // itself mean, and it has to work from the composer -- which is where the user
  // spends most of their time and where they are most likely to want it.
  useHotkey(
    { key: "k", mod: true, whileTyping: true },
    useCallback(() => setPaletteOpen((open) => !open), []),
  );
  useHotkey(
    { key: "b", mod: true, whileTyping: true },
    useCallback(() => setRailHidden((hidden) => !hidden), [setRailHidden]),
  );

  // strict:false because this layout renders above /app, /app/p/$pid and
  // /app/p/$pid/t/$tid, and only some of those have each param.
  const { pid, tid } = useParams({ strict: false });

  return (
    <RequireSession>
      <ToastProvider>
        <div className="flex h-screen bg-background text-foreground">
          <Sidebar
            open={menuOpen}
            collapsed={railHidden}
            onClose={() => setMenuOpen(false)}
            header={
              <>
                <div className="flex items-center gap-1">
                  <Link
                    to="/app"
                    className="flex min-w-0 flex-1 items-center gap-2 rounded-md px-2 py-1 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  >
                    <span aria-hidden className="size-2 shrink-0 rounded-full bg-brand" />
                    <span className="font-display truncate text-[15px] font-semibold tracking-tight">
                      Sentient
                    </span>
                  </Link>
                  <IconButton
                    icon={PanelLeft}
                    label="Hide the sidebar"
                    onClick={() => setRailHidden(true)}
                    className="hidden md:grid"
                  />
                </div>

                {/*
                  The palette's own entry point, and the reason it is discoverable
                  at all. A keyboard shortcut nobody is told about is a feature for
                  the person who wrote it; the shortcut is printed on the control
                  so the fast path is learned from the slow one.
                */}
                <button
                  type="button"
                  onClick={() => setPaletteOpen(true)}
                  className="mt-3 flex w-full items-center gap-2 rounded-md border border-sidebar-border bg-background/40 px-2.5 py-1.5 text-sm text-muted-foreground transition-colors duration-[--duration-instant] hover:border-border hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  <Search className="size-3.5 shrink-0" />
                  <span className="flex-1 text-left">Search…</span>
                  <Kbd>{PALETTE_HINT}</Kbd>
                </button>

                <nav aria-label="Account" className="mt-3 flex flex-col gap-0.5">
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
            footer={
              <>
                <FooterLinks />
                <UserRow />
              </>
            }
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
            {/*
              Two reasons this bar exists, and it renders when EITHER holds: the
              drawer toggle below md, and the way back from a hidden rail above it.
              Hiding the rail with no visible control to bring it back is the one
              thing a collapse must never do -- the shortcut alone is not a way
              back for someone who collapsed it by clicking.
            */}
            <div
              className={`sticky top-0 z-sticky flex items-center gap-2 border-b border-border bg-background/85 px-3 py-2 backdrop-blur ${
                railHidden ? "" : "md:hidden"
              }`}
            >
              <IconButton
                icon={MenuIcon}
                label="Open menu"
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen(true)}
                className="md:hidden"
              />
              {railHidden && (
                <IconButton
                  icon={PanelLeft}
                  label="Show the sidebar"
                  onClick={() => setRailHidden(false)}
                  className="hidden md:grid"
                />
              )}
              <span className="font-display text-sm font-semibold tracking-tight md:hidden">
                Sentient
              </span>
              <button
                type="button"
                onClick={() => setPaletteOpen(true)}
                aria-label="Search projects and actions"
                className="ml-auto grid size-8 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                <Search className="size-4" />
              </button>
            </div>
            <Outlet />
          </main>

          <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
        </div>
      </ToastProvider>
    </RequireSession>
  );
}

/**
 * Who is signed in, and the way out. It shows the identity because a console
 * that holds provider keys and mints API keys is one where "which account am I
 * in" is a question worth being able to answer without leaving the page.
 *
 * Sign out is in a menu now rather than beside the address. It was a bare text
 * button one tab stop from the theme toggle, sized like a caption -- an
 * irreversible action given the least weight of any control in the rail.
 */
/**
 * Where a user goes when something is wrong, and where the legal documents are.
 *
 * "My NPC won't talk" previously had nowhere to go from inside the product,
 * which meant the report never arrived and the answer never got written down.
 * The issue link is the template chooser, not a blank issue, because the
 * template asks for the five things that would otherwise cost a second round
 * trip.
 */
function FooterLinks() {
  const links = [
    { label: "Support", href: ISSUES_URL },
    { label: "Privacy", href: PRIVACY_URL },
    { label: "Terms", href: TERMS_URL },
  ];

  return (
    <nav className="flex flex-wrap items-center gap-x-3 gap-y-1 px-1 pb-2 text-[11px]">
      {links.map((link) => (
        <a
          key={link.label}
          href={link.href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-muted-foreground transition-colors hover:text-sidebar-foreground"
        >
          {link.label}
        </a>
      ))}
    </nav>
  );
}

function UserRow() {
  const signOut = useSignOut();
  const { data } = useSession();
  const email = data?.user?.email;

  return (
    <div className="flex items-center gap-2 rounded-md px-1 py-0.5">
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
      <Menu
        label="Account"
        items={[{ label: "Sign out", icon: LogOut, onSelect: () => void signOut() }]}
      />
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
        <button
          type="button"
          className="text-sm underline underline-offset-4"
          onClick={() => void signOut()}
        >
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
