import type { ReactNode } from "react";
import { twMerge } from "tailwind-merge";

const TONE = {
  neutral: "bg-muted text-muted-foreground",
  brand: "bg-brand/10 text-brand",
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  danger: "bg-destructive/10 text-destructive",
} as const;

/**
 * The status pill `DocumentRow` hand-rolled, spelled once so the key list, the
 * document list and the rail cannot drift into three shapes for one idea.
 *
 * Every tone is a 10% tint of a token measured in `tokens.css` against that
 * tint, not a Tailwind palette shade. Four hardcoded shades were failing WCAG AA
 * on this surface before those tokens existed; reintroducing one here would undo
 * that silently.
 */
export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: keyof typeof TONE;
  className?: string;
}) {
  return (
    <span
      className={twMerge(
        "inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        TONE[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
