import { MoreHorizontal, type LucideIcon } from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { twMerge } from "tailwind-merge";

/** One row of a menu. `danger` is the destructive tone, not a separate component. */
export type MenuItem = {
  label: string;
  onSelect: () => void;
  icon?: LucideIcon;
  /** Rendered right-aligned in the mono face. A hint, never the only way in. */
  shortcut?: string;
  danger?: boolean;
  disabled?: boolean;
};

/**
 * An overflow menu built on the native Popover API, for the same reason `Modal`
 * is built on the native `<dialog>`: `popover="auto"` puts the panel in the TOP
 * LAYER and gives light-dismiss (outside click) and Escape for free.
 *
 * The top layer is not a nicety here, it is the requirement. The rail's scroll
 * container is `overflow-y-auto`, so an absolutely-positioned panel would be
 * clipped by it -- the exact failure the design guidance calls out. A top-layer
 * element is not painted as a descendant of its scroll ancestor at all, so no
 * `overflow` on any ancestor can reach it.
 *
 * Position is computed in JS rather than with CSS anchor positioning, which is
 * still Chromium-only. The UA stylesheet gives an open popover `inset: 0` and
 * `margin: auto` to centre it, so `inset-auto m-0` has to come off before the
 * measured coordinates mean anything.
 *
 * Domain-free: it takes labels and callbacks and knows nothing about projects.
 */
export function Menu({
  items,
  label,
  align = "end",
  trigger,
  className,
}: {
  items: MenuItem[];
  /** Accessible name for the default trigger. Required -- an unlabelled `⋯` is a dead end for a screen reader. */
  label: string;
  align?: "start" | "end";
  /** Replaces the default `⋯` button. Gets the popover wiring applied to it. */
  trigger?: ReactNode;
  className?: string;
}) {
  const id = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);

  const place = useCallback(() => {
    const panel = panelRef.current;
    const anchor = triggerRef.current;
    if (!panel || !anchor) return;

    const a = anchor.getBoundingClientRect();
    const p = panel.getBoundingClientRect();
    const GAP = 6;
    const EDGE = 8;

    // Below the trigger, flipping above only when there is genuinely no room --
    // a menu that flips on a near-miss reads as jitter.
    const below = a.bottom + GAP;
    const top = below + p.height > window.innerHeight - EDGE ? a.top - GAP - p.height : below;

    const raw = align === "end" ? a.right - p.width : a.left;
    const left = Math.min(Math.max(raw, EDGE), window.innerWidth - p.width - EDGE);

    panel.style.top = `${Math.max(top, EDGE)}px`;
    panel.style.left = `${left}px`;
  }, [align]);

  // `toggle` rather than a click handler: light-dismiss and Escape close the
  // popover WITHOUT going through any handler of ours, so this is the only event
  // that sees every open and every close.
  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;
    const onToggle = (event: Event) => {
      const isOpen = (event as ToggleEvent).newState === "open";
      setOpen(isOpen);
      if (isOpen) {
        place();
        // Focus the first enabled item so the menu is immediately keyboard-driven.
        panel.querySelector<HTMLButtonElement>("button:not([disabled])")?.focus();
      }
    };
    panel.addEventListener("toggle", onToggle);
    return () => panel.removeEventListener("toggle", onToggle);
  }, [place]);

  // A popover does not move with the page, so a scroll or resize would leave it
  // stranded beside the row it belongs to. Repositioning is cheaper and less
  // surprising than closing on scroll, which loses the user's intent.
  useEffect(() => {
    if (!open) return;
    const onChange = () => place();
    window.addEventListener("scroll", onChange, true);
    window.addEventListener("resize", onChange);
    return () => {
      window.removeEventListener("scroll", onChange, true);
      window.removeEventListener("resize", onChange);
    };
  }, [open, place]);

  const close = () => panelRef.current?.hidePopover();

  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const buttons = Array.from(
      panelRef.current?.querySelectorAll<HTMLButtonElement>("button:not([disabled])") ?? [],
    );
    if (buttons.length === 0) return;
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement);

    const focus = (next: number) => {
      event.preventDefault();
      buttons[(next + buttons.length) % buttons.length].focus();
    };

    if (event.key === "ArrowDown") focus(index + 1);
    else if (event.key === "ArrowUp") focus(index - 1);
    else if (event.key === "Home") focus(0);
    else if (event.key === "End") focus(buttons.length - 1);
  };

  return (
    <>
      {trigger ? (
        <span
          ref={(node) => {
            triggerRef.current = node?.querySelector("button") ?? null;
          }}
          // The wrapper carries the popover wiring so a caller can pass any
          // trigger without knowing the popover id.
          onClick={() => panelRef.current?.togglePopover()}
          className="contents"
        >
          {trigger}
        </span>
      ) : (
        <button
          ref={triggerRef}
          type="button"
          aria-label={label}
          aria-haspopup="menu"
          aria-expanded={open}
          popoverTarget={id}
          className={twMerge(
            "grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors duration-[--duration-instant] hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
            open && "bg-muted text-foreground",
            className,
          )}
        >
          <MoreHorizontal className="size-4" />
        </button>
      )}

      <div
        ref={panelRef}
        id={id}
        popover="auto"
        role="menu"
        aria-label={label}
        onKeyDown={onKeyDown}
        className="fixed inset-auto m-0 min-w-48 rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-elevated backdrop:bg-transparent"
      >
        {items.map((item) => (
          <button
            key={item.label}
            type="button"
            role="menuitem"
            disabled={item.disabled}
            onClick={() => {
              close();
              item.onSelect();
            }}
            className={twMerge(
              "flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-left text-sm transition-colors duration-[--duration-instant] focus-visible:outline-none disabled:pointer-events-none disabled:opacity-40",
              item.danger
                ? "text-destructive hover:bg-destructive/10 focus-visible:bg-destructive/10"
                : "text-foreground hover:bg-muted focus-visible:bg-muted",
            )}
          >
            {item.icon && <item.icon className="size-4 shrink-0 opacity-70" />}
            <span className="flex-1 truncate">{item.label}</span>
            {item.shortcut && (
              <span className="font-mono text-[11px] text-muted-foreground">{item.shortcut}</span>
            )}
          </button>
        ))}
      </div>
    </>
  );
}
