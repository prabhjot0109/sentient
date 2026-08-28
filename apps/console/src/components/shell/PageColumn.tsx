import type { ReactNode } from "react";
import { twMerge } from "tailwind-merge";

/**
 * The centred reading column every page inside /app renders into.
 *
 * `w-full` is the reason this exists as a component instead of a copied class
 * string. Its parent `<main>` is `flex flex-col`, and a flex item is stretched
 * to fill the cross axis only when NEITHER cross-axis margin is auto (CSS
 * Flexbox 9.6). `mx-auto` sets both, so stretch silently stops applying and the
 * column sizes to its own content.
 *
 * That is not a subtle few-pixel difference. Measured in headless Chrome at a
 * 1400px viewport: a transcript whose longest line is a short NPC reply rendered
 * the column at 122.875px, against 765px once `w-full` was restored. The chat
 * collapsed to narrower than a phone the moment an answer arrived, and it did it
 * on all four project routes, because every one of them had copied the same
 * `mx-auto max-w-3xl` string from its neighbour.
 *
 * So the constraint lives here once. A new route uses this and cannot
 * reintroduce the bug by copying a sibling.
 */
export function PageColumn({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={twMerge("mx-auto w-full max-w-3xl px-6 md:px-10", className)}>{children}</div>
  );
}
