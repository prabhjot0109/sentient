import type { ReactNode } from "react";

/**
 * Layout only. It does not know what a project is, which is what lets F5 nest
 * threads inside project rows without touching this file.
 *
 * A drawer below md, a rail above. The closed drawer is `hidden` rather than
 * translated off-screen on purpose: an off-screen aside is still in the tab
 * order, so a keyboard user on a phone tabs through a menu they cannot see
 * before reaching the page. display:none removes it from the tab order, and it
 * costs the slide animation, which is the cheaper thing to lose.
 */
export function Sidebar({
  children,
  footer,
  open,
  onClose,
}: {
  children: ReactNode;
  footer: ReactNode;
  open: boolean;
  onClose: () => void;
}) {
  return (
    <>
      {open && (
        <button
          type="button"
          aria-label="Close menu"
          onClick={onClose}
          className="fixed inset-0 z-30 bg-black/60 md:hidden"
        />
      )}
      <aside
        className={`${
          open ? "fixed inset-y-0 left-0 z-40 flex" : "hidden"
        } w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:static md:flex`}
      >
        <div className="flex-1 overflow-y-auto p-3">{children}</div>
        <div className="border-t border-sidebar-border p-3">{footer}</div>
      </aside>
    </>
  );
}
