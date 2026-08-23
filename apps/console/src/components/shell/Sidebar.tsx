import type { ReactNode } from "react";

/**
 * Layout only. It does not know what a project is, which is what lets F5 nest
 * threads inside project rows without touching this file.
 */
export function Sidebar({ children, footer }: { children: ReactNode; footer: ReactNode }) {
  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
      <div className="flex-1 overflow-y-auto p-3">{children}</div>
      <div className="border-t border-sidebar-border p-3">{footer}</div>
    </aside>
  );
}
