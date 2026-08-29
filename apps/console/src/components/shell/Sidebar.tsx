import type { ReactNode } from "react";

/**
 * Layout only. It does not know what a project is, which is what lets the
 * projects feature nest threads inside project rows without touching this file.
 *
 * A drawer below md, a rail above. The closed drawer is `hidden` rather than
 * translated off-screen on purpose: an off-screen aside is still in the tab
 * order, so a keyboard user on a phone tabs through a menu they cannot see
 * before reaching the page. display:none removes it from the tab order, and it
 * costs the slide animation, which is the cheaper thing to lose.
 *
 * `collapsed` is the DESKTOP axis and is independent of `open`, which is the
 * mobile one. They cannot be one flag: a phone's drawer is closed by default and
 * a desktop rail is open by default, so a single boolean would have to mean the
 * opposite thing at each end of the breakpoint. The shell keeps a way back
 * visible whenever this is true -- a collapse with no visible expand is a trap.
 */
export function Sidebar({
  header,
  children,
  footer,
  open,
  collapsed,
  onClose,
}: {
  header: ReactNode;
  children: ReactNode;
  footer: ReactNode;
  open: boolean;
  collapsed: boolean;
  onClose: () => void;
}) {
  return (
    <>
      {open && (
        <button
          type="button"
          aria-label="Close menu"
          onClick={onClose}
          className="fixed inset-0 z-drawer-scrim bg-black/60 md:hidden"
        />
      )}
      <aside
        className={`${open ? "fixed inset-y-0 left-0 z-drawer flex" : "hidden"} ${
          collapsed ? "md:hidden" : "md:flex"
        } w-[260px] shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:static`}
      >
        <div className="px-3 pt-3 pb-2">{header}</div>
        <div className="flex-1 overflow-y-auto px-2 pb-3">{children}</div>
        <div className="border-t border-sidebar-border p-2.5">{footer}</div>
      </aside>
    </>
  );
}
