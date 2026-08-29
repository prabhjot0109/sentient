import { useNavigate, useParams } from "@tanstack/react-router";
import {
  FileText,
  KeyRound,
  LogOut,
  MessageSquarePlus,
  Moon,
  Pencil,
  Search,
  SlidersHorizontal,
  Sun,
  Trash2,
  Vault,
  type LucideIcon,
} from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useMemo, useRef, useState } from "react";

import { Kbd, MOD } from "@/components/ui/Kbd";
import { Modal } from "@/components/ui/Modal";
import { useSignOut } from "@/features/auth";
import { DeleteProjectDialog, RenameProjectDialog, useProjects } from "@/features/projects";

import { rank } from "../filter";

type Command = {
  id: string;
  label: string;
  group: string;
  keywords?: string;
  icon: LucideIcon;
  /** Right-aligned context: which preset a project uses, which group a command is in. */
  hint?: string;
  danger?: boolean;
  run: () => void;
};

/**
 * Every action in the console, reachable from one keystroke.
 *
 * It is here for a specific reason rather than as a fashion. Before this, four
 * of the console's operations had exactly ONE route each -- rename and delete a
 * project, rename and delete a conversation -- and that route was a 22px icon
 * held at zero opacity until its row was hovered. A single point of access to an
 * action is a design risk on its own: when it is missed, the action does not
 * read as hard to find, it reads as absent. So the row menus are the primary
 * path and this is the second one, and neither is load-bearing alone.
 *
 * It hosts the project rename and delete dialogs itself rather than reaching
 * into the rail. The rail only renders a menu for a project it is currently
 * drawing; the palette acts on the OPEN project whether or not that row is
 * scrolled into view, so it needs its own.
 */
export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const [dialog, setDialog] = useState<"none" | "rename" | "delete">("none");
  const listRef = useRef<HTMLUListElement>(null);

  const navigate = useNavigate();
  const signOut = useSignOut();
  const { theme, setTheme } = useTheme();
  const { data: projects = [] } = useProjects();
  // strict:false -- the palette is mounted above every route in /app and only
  // some of them carry a project id.
  const { pid } = useParams({ strict: false });
  const current = projects.find((project) => project.id === pid);

  // Reset on every open. A palette that reopens onto the previous query is
  // remembering something the user has already finished with.
  useEffect(() => {
    if (open) {
      setQuery("");
      setCursor(0);
    }
  }, [open]);

  const commands = useMemo<Command[]>(() => {
    const list: Command[] = [];

    if (current) {
      const pidParams = { pid: current.id };
      list.push(
        {
          id: "chat",
          label: "New conversation",
          group: current.name,
          keywords: "chat talk npc message",
          icon: MessageSquarePlus,
          run: () => void navigate({ to: "/app/p/$pid", params: pidParams }),
        },
        {
          id: "lore",
          label: "Lore",
          group: current.name,
          keywords: "documents upload pdf files",
          icon: FileText,
          run: () => void navigate({ to: "/app/p/$pid/documents", params: pidParams }),
        },
        {
          id: "settings",
          label: "Settings",
          group: current.name,
          keywords: "model persona voice temperature config",
          icon: SlidersHorizontal,
          run: () => void navigate({ to: "/app/p/$pid/settings", params: pidParams }),
        },
        {
          id: "rename",
          label: "Rename this project",
          group: current.name,
          icon: Pencil,
          run: () => setDialog("rename"),
        },
        {
          id: "delete",
          label: "Delete this project",
          group: current.name,
          icon: Trash2,
          danger: true,
          run: () => setDialog("delete"),
        },
      );
    }

    for (const project of projects) {
      if (project.id === pid) continue;
      list.push({
        id: `open-${project.id}`,
        label: project.name,
        group: "Switch project",
        keywords: project.base_preset,
        icon: MessageSquarePlus,
        hint: project.base_preset,
        run: () => void navigate({ to: "/app/p/$pid", params: { pid: project.id } }),
      });
    }

    list.push(
      {
        id: "keys",
        label: "API keys",
        group: "Go to",
        keywords: "mantella token",
        icon: KeyRound,
        run: () => void navigate({ to: "/app/keys" }),
      },
      {
        id: "credentials",
        label: "Provider keys",
        group: "Go to",
        keywords: "vault openai groq gemini secret",
        icon: Vault,
        run: () => void navigate({ to: "/app/credentials" }),
      },
      {
        id: "theme",
        label: theme === "dark" ? "Switch to the light theme" : "Switch to the dark theme",
        group: "Account",
        keywords: "theme dark light appearance",
        icon: theme === "dark" ? Sun : Moon,
        run: () => setTheme(theme === "dark" ? "light" : "dark"),
      },
      {
        id: "signout",
        label: "Sign out",
        group: "Account",
        keywords: "logout leave",
        icon: LogOut,
        run: () => void signOut(),
      },
    );

    return list;
  }, [current, navigate, pid, projects, setTheme, signOut, theme]);

  const results = useMemo(() => rank(query, commands), [query, commands]);
  // Clamped rather than reset: typing a character that narrows the list should
  // not throw away a selection that is still in it.
  const active = Math.min(cursor, Math.max(results.length - 1, 0));

  // Keep the highlighted row on screen when it moves by keyboard. `nearest`, so
  // arrowing within the visible window does not scroll at all.
  useEffect(() => {
    listRef.current?.children[active]?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const runActive = () => {
    const command = results[active];
    if (!command) return;
    // Close FIRST. A command that navigates would otherwise unmount this tree
    // mid-handler, and a command that opens a dialog needs the palette gone
    // before a second <dialog> is shown over it.
    onClose();
    command.run();
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (results.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setCursor((index) => (Math.min(index, results.length - 1) + 1) % results.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setCursor(
        (index) => (Math.min(index, results.length - 1) - 1 + results.length) % results.length,
      );
    } else if (event.key === "Enter") {
      event.preventDefault();
      runActive();
    }
  };

  return (
    <>
      <Modal open={open} onClose={onClose} title="Command palette" titleHidden size="palette">
        <div className="flex items-center gap-3 border-b border-border px-4">
          <Search className="size-4 shrink-0 text-muted-foreground" />
          <input
            autoFocus
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setCursor(0);
            }}
            onKeyDown={onKeyDown}
            placeholder="Search projects and actions…"
            aria-label="Search projects and actions"
            // A combobox, so a screen reader is told the list below is the result
            // of what is being typed rather than unrelated content.
            role="combobox"
            aria-expanded
            aria-controls="command-results"
            aria-activedescendant={results[active] ? `command-${results[active].id}` : undefined}
            className="w-full bg-transparent py-3.5 text-[15px] placeholder:text-muted-foreground focus:outline-none"
          />
        </div>

        {results.length === 0 ? (
          <p className="px-4 py-10 text-center text-sm text-muted-foreground">
            Nothing matches that.
          </p>
        ) : (
          <ul
            id="command-results"
            ref={listRef}
            role="listbox"
            aria-label="Commands"
            className="max-h-80 overflow-y-auto p-2"
          >
            {results.map((command, index) => (
              <li
                key={command.id}
                id={`command-${command.id}`}
                role="option"
                aria-selected={index === active}
              >
                {/*
                  A button inside the option rather than a clickable <li>: the row
                  has to be reachable by pointer while the keyboard drives it
                  through aria-activedescendant, and only a real button gives the
                  pointer path its own semantics.

                  onMouseMove, not onMouseEnter. The list scrolls under a
                  STATIONARY pointer while arrowing, and enter alone would then
                  hand the selection back to whatever row slid beneath the cursor.
                */}
                <button
                  type="button"
                  tabIndex={-1}
                  onMouseMove={() => setCursor(index)}
                  onClick={runActive}
                  className={`flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-left text-sm transition-colors duration-[--duration-instant] ${
                    index === active ? "bg-muted" : ""
                  } ${command.danger ? "text-destructive" : "text-foreground"}`}
                >
                  <command.icon className="size-4 shrink-0 opacity-70" />
                  <span className="min-w-0 flex-1 truncate">{command.label}</span>
                  <span className="shrink-0 truncate text-xs text-muted-foreground">
                    {command.hint ?? command.group}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="flex items-center gap-4 border-t border-border px-4 py-2.5 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Kbd>↑</Kbd>
            <Kbd>↓</Kbd> to move
          </span>
          <span className="flex items-center gap-1.5">
            <Kbd>↵</Kbd> to run
          </span>
          <span className="ml-auto flex items-center gap-1.5">
            <Kbd>Esc</Kbd> to close
          </span>
        </div>
      </Modal>

      {/*
        Outside the palette's own <Modal>, so the palette is closed by the time
        either of these opens. Two dialogs in the top layer at once leaves the
        second showing over an inert first, and dismissing it returns focus to a
        panel the user has already finished with.
      */}
      {current && (
        <>
          <RenameProjectDialog
            project={current}
            open={dialog === "rename"}
            onClose={() => setDialog("none")}
          />
          <DeleteProjectDialog
            project={current}
            open={dialog === "delete"}
            onClose={() => setDialog("none")}
            onDeleted={() => void navigate({ to: "/app" })}
          />
        </>
      )}
    </>
  );
}

/** Exported for the rail's own trigger, so the two cannot describe the key differently. */
export const PALETTE_HINT = `${MOD} K`;
