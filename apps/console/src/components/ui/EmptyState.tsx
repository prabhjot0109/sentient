import type { ReactNode } from "react";

/**
 * The dashed-card shape DocumentsEmptyState hand-rolled.
 *
 * ProjectsEmptyState deliberately does NOT use this: it is a page-level
 * onboarding block whose body carries inline markup ("a project is <strong>one
 * game</strong>") and an embedded dialog trigger, and flattening that into a
 * `body` string would strip the emphasis that makes the sentence readable.
 * Two shapes that look alike in a plan are not always one component.
 */
export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-md border border-dashed border-border p-6 text-center">
      <p className="text-sm font-medium">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{body}</p>
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
