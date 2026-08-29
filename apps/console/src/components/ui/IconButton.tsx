import type { LucideIcon } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";
import { twMerge } from "tailwind-merge";

/**
 * A square, icon-only control with a real hit target.
 *
 * It exists because the console's hand-rolled icon buttons were `p-1` around a
 * `size-3.5` glyph -- a 22px target, under every published minimum -- and were
 * held at `opacity-0` until the row was hovered. Two invisible 22px controls at
 * the right edge of a 256px rail are not a discoverable affordance, which is why
 * the project and conversation rows now reach their actions through `Menu`
 * instead.
 *
 * `size-8` is 32px, which clears the 24px CSS-pixel minimum in WCAG 2.2 Target
 * Size (Minimum) with margin, and the glyph stays 16px so the visual weight is
 * unchanged from what it replaces.
 */
export function IconButton({
  icon: Icon,
  label,
  className,
  type = "button",
  ...rest
}: {
  icon: LucideIcon;
  /** The accessible name. Not optional: an icon alone names nothing. */
  label: string;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      className={twMerge(
        "grid size-8 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors duration-[--duration-instant] hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:pointer-events-none disabled:opacity-40",
        className,
      )}
      {...rest}
    >
      <Icon className="size-4" />
    </button>
  );
}
