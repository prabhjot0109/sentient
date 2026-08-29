import { AlertTriangle, Check, X } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

type Tone = "success" | "failure";

type Toast = { id: number; title: string; body?: string; tone: Tone };

/**
 * Confirmation for work that leaves no trace on screen.
 *
 * Renaming a project changed a label the user was already looking at, so it
 * confirmed itself. Revoking a key, storing a provider credential and deleting a
 * document did not: the dialog closed and a row changed somewhere the user was
 * not looking, which is indistinguishable from nothing having happened. That is
 * the gap this fills, and it is the reason it is deliberately NOT used for
 * anything whose result is already visible -- a toast for an outcome you can see
 * is noise, and noise is what makes people stop reading toasts.
 *
 * Errors keep rendering in place through `ErrorState`. A failure the user has to
 * act on must not be on a timer.
 */
const ToastContext = createContext<((toast: Omit<Toast, "id">) => void) | null>(null);

const DURATION_MS = 5000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback(
    (toast: Omit<Toast, "id">) => {
      const id = nextId.current++;
      setToasts((current) => [...current, { ...toast, id }]);
      window.setTimeout(() => dismiss(id), DURATION_MS);
    },
    [dismiss],
  );

  // The context value is the push function itself rather than an object, so a
  // consumer cannot re-render on a change to a sibling field that does not exist.
  const value = useMemo(() => push, [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {/*
        `aria-live="polite"` on the CONTAINER, not on each toast. A live region
        has to be in the DOM before the content it announces arrives; announcing
        from a region that mounts with its message is unreliable in every screen
        reader.
      */}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-0 z-toast flex flex-col items-center gap-2 p-4 sm:items-end sm:p-6"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className="pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-lg border border-border bg-popover p-3 text-popover-foreground shadow-elevated motion-safe:animate-[toast-in_var(--duration-base)_var(--ease-out-quart)]"
          >
            {toast.tone === "success" ? (
              <Check className="mt-0.5 size-4 shrink-0 text-success" />
            ) : (
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
            )}
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{toast.title}</p>
              {toast.body && <p className="mt-0.5 text-xs text-muted-foreground">{toast.body}</p>}
            </div>
            <button
              type="button"
              aria-label="Dismiss"
              onClick={() => dismiss(toast.id)}
              className="-m-1 grid size-6 shrink-0 place-items-center rounded text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              <X className="size-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

/**
 * Throws outside the provider rather than returning a no-op. A silently
 * swallowed confirmation is the failure this component exists to prevent.
 */
export function useToast() {
  const push = useContext(ToastContext);
  if (!push) throw new Error("useToast must be used inside <ToastProvider>.");
  return push;
}
