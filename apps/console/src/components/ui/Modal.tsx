import { useEffect, useRef, type ReactNode } from "react";
import { twMerge } from "tailwind-merge";

const SIZE = {
  md: "max-w-md",
  lg: "max-w-lg",
  /** The command palette. Wide enough to read a project name and a hint on one line. */
  palette: "max-w-xl",
} as const;

/**
 * Built on the native <dialog> rather than a hand-rolled overlay. showModal()
 * gives the focus trap, Escape-to-close, inert background and top-layer stacking
 * for free; reimplementing those correctly is more code than this whole file and
 * is usually reimplemented wrong.
 *
 * Domain-free on purpose -- components/ui may not know what a project is.
 *
 * ONE dialog implementation, not two. The command palette wants a different
 * shape -- wider, its own header, no `<h2>` above the input -- and the product
 * register is explicit that two components for one idea is how a surface starts
 * feeling untrustworthy. So the shape is parameterised and the behaviour is
 * shared: `titleHidden` keeps the accessible name while removing the visible
 * heading, and `bodyClassName` lets the palette drop the padding it fills itself.
 */
export function Modal({
  open,
  onClose,
  title,
  titleHidden = false,
  size = "md",
  className,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  titleHidden?: boolean;
  size?: keyof typeof SIZE;
  className?: string;
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
      //
      // The guard is for the OTHER direction. `close()` does not fire its event
      // synchronously, it QUEUES one -- so an effect that closes and immediately
      // reopens the dialog still leaves a `close` event in flight, and by the
      // time it lands the dialog is open again. React cannot tell that event
      // from a real dismissal, so it tore the whole dialog down.
      //
      // StrictMode does exactly that on every dialog that mounts ALREADY open
      // (`<Modal open>` rather than `<Modal open={state}>`): the double-invoked
      // unmount guard below closes it, the effect above reopens it, and the
      // queued event then reported a dismissal the user never made. Six dialogs
      // mount that way and none of them could be opened in dev.
      //
      // A close that leaves the dialog OPEN is therefore ours; only a real
      // dismissal leaves it closed.
      onClose={() => {
        if (ref.current?.open) return;
        onClose();
      }}
      onClick={(event) => {
        // The backdrop is part of the <dialog> box, so a click that lands on the
        // element itself rather than on its content is a backdrop click.
        if (event.target === ref.current) onClose();
      }}
      className={twMerge(
        "m-auto w-[calc(100%-2rem)] rounded-xl border border-border bg-card p-0 text-card-foreground shadow-elevated backdrop:bg-black/50 backdrop:backdrop-blur-[2px] open:motion-safe:animate-[overlay-in_var(--duration-fast)_var(--ease-out-quart)]",
        SIZE[size],
        className,
      )}
    >
      {/*
        Padding lives on an inner element rather than on the <dialog> itself.
        On the dialog it made every click in the 24px gutter land on the element
        and read as a backdrop click, so the panel closed when a user pressed
        just outside a field they were aiming for.
      */}
      <div className={size === "palette" ? "" : "p-6"}>
        <h2 className={titleHidden ? "sr-only" : "mb-4 text-lg font-semibold"}>{title}</h2>
        {children}
      </div>
    </dialog>
  );
}
