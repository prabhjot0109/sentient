/**
 * A key cap. Rendered from the platform's own modifier so a Mac user is not told
 * to press Ctrl: `⌘` and `Ctrl` are different keys, and printing the wrong one
 * is worse than printing none.
 */
export const MOD =
  typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform)
    ? "\u2318"
    : "Ctrl";

export function Kbd({ children }: { children: string }) {
  return (
    <kbd className="font-mono inline-flex h-5 min-w-5 items-center justify-center rounded border border-border bg-muted px-1.5 text-[11px] font-medium text-muted-foreground">
      {children}
    </kbd>
  );
}
