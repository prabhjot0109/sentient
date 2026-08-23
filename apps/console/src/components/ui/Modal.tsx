import { useEffect, useRef, type ReactNode } from "react";

/**
 * Built on the native <dialog> rather than a hand-rolled overlay. showModal()
 * gives the focus trap, Escape-to-close, inert background and top-layer stacking
 * for free; reimplementing those correctly is more code than this whole file and
 * is usually reimplemented wrong.
 *
 * Domain-free on purpose -- components/ui may not know what a project is.
 */
export function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    // showModal() throws on an already-open dialog, and close() on a closed one
    // is a no-op that still fires nothing. Both guards are load-bearing.
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  // Unmounting an OPEN dialog removes it from the DOM without closing it, which
  // can strand the top-layer and backdrop state. KeysScreen unmounts the reveal
  // rather than toggling it, so this is reached in practice.
  useEffect(() => {
    const dialog = ref.current;
    return () => {
      if (dialog?.open) dialog.close();
    };
  }, []);

  return (
    <dialog
      ref={ref}
      // Escape closes the dialog without React knowing. Without this the state
      // stays "open" and the next open() is a no-op -- the dialog never reappears.
      onClose={onClose}
      onClick={(event) => {
        // The backdrop is part of the <dialog> box, so a click that lands on the
        // element itself rather than on its content is a backdrop click.
        if (event.target === ref.current) onClose();
      }}
      className="m-auto w-full max-w-md rounded-lg border border-border bg-card p-6 text-card-foreground shadow-lg backdrop:bg-black/40"
    >
      <h2 className="mb-4 text-lg font-semibold">{title}</h2>
      {children}
    </dialog>
  );
}
