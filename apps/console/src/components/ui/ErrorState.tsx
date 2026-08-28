import type { ReactNode } from "react";

import { describe } from "@/lib/api/messages";
import type { ErrorTone } from "@/lib/api/messages";

const TONE: Record<ErrorTone, string> = {
  info: "border-border bg-card text-foreground",
  warning: "border-warning/40 bg-warning/10 text-foreground",
  failure: "border-destructive/40 bg-destructive/10 text-foreground",
};

/**
 * Takes the error, not the copy. If it took copy, a call site could pass its own
 * strings and quietly re-fork the map that lib/api/messages.ts exists to hold --
 * which is exactly how three duplicate `message()` helpers appeared before F9.
 */
export function ErrorState({
  error,
  size = "inline",
  action,
}: {
  error: unknown;
  size?: "inline" | "page";
  action?: ReactNode;
}) {
  const copy = describe(error);

  if (size === "page") {
    return (
      <div className="mx-auto max-w-md space-y-2 p-8 text-center" role="alert">
        <h1 className="text-lg font-semibold">{copy.title}</h1>
        <p className="text-sm text-muted-foreground">{copy.body}</p>
        {action && <div className="pt-2">{action}</div>}
      </div>
    );
  }

  return (
    <div className={`rounded-md border p-3 text-sm ${TONE[copy.tone]}`} role="alert">
      <p className="font-medium">{copy.title}</p>
      <p className="mt-1 text-muted-foreground">{copy.body}</p>
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
