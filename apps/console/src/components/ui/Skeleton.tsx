import { twMerge } from "tailwind-merge";

/**
 * The loading state for content whose SHAPE is known before its values are.
 *
 * It replaces the console's "Loading projects…" / "Loading keys…" / "Loading…"
 * paragraphs, which were four different sentences for one state and moved the
 * layout twice: once when the sentence appeared, once when the real rows pushed
 * it out. A skeleton occupies the space the rows will occupy, so the arrival is
 * a fill rather than a jump.
 *
 * `animate-pulse` only -- no shimmer sweep. A travelling highlight is decorative
 * motion, and the reduced-motion block in tokens.css already stops the pulse for
 * anyone who has asked for that.
 */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={twMerge("animate-pulse rounded-md bg-muted", className)} />;
}

/** N stacked rows at a shared height, for a list whose length is not yet known. */
export function SkeletonRows({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div className="space-y-2" role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className={twMerge("h-9 w-full", className)} />
      ))}
    </div>
  );
}
