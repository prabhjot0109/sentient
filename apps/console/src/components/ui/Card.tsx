import type { HTMLAttributes } from "react";
import { twMerge } from "tailwind-merge";

/**
 * A bordered panel. 28 className strings started with "rounded-md border"; this
 * is what they had in common. bg-card rather than transparent, so a panel reads
 * as raised against the near-black background rather than merely outlined.
 */
export function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={twMerge("rounded-md border border-border bg-card p-4", className)} {...rest} />
  );
}
