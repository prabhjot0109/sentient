import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

/**
 * Two states, not three. `enableSystem` is off in main.tsx, so "system" is not
 * a value this app can hold and a three-way control would offer a setting that
 * does nothing.
 *
 * The `mounted` gate is not ceremony. On the first render next-themes has not
 * read localStorage yet, so `theme` is undefined and any icon chosen from it is
 * a guess that flips a frame later. Rendering a same-sized blank until then
 * costs one frame and avoids the flicker; the button keeps its label throughout
 * so a screen reader is never handed an unlabelled control.
 */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={mounted ? `Switch to ${isDark ? "light" : "dark"} theme` : "Switch theme"}
      title={mounted ? `Switch to ${isDark ? "light" : "dark"} theme` : undefined}
      className="grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      {mounted && (isDark ? <Sun className="size-4" /> : <Moon className="size-4" />)}
    </button>
  );
}
