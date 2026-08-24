import type { ReactNode } from "react";

/**
 * One config row.
 *
 * `value === null` means UNSET, not "the default happens to be this" -- the
 * backend reports the config AS STORED for exactly this reason. Rendering a
 * resolved default into an input would pin a value the user never chose, and the
 * next save would write it. So an unset field shows its placeholder and the
 * "Using the server default" note, and the Clear control is how you get back
 * there.
 */
export function ConfigField({
  label,
  hint,
  value,
  onClear,
  children,
}: {
  label: string;
  hint?: string;
  value: string | number | null;
  onClear: () => void;
  children: ReactNode;
}) {
  return (
    <div className="grid grid-cols-[14rem_1fr] items-start gap-4 border-b border-border py-3 last:border-0">
      <div>
        <p className="text-sm font-medium">{label}</p>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
      <div className="space-y-1">
        {children}
        {value === null ? (
          <p className="text-xs text-muted-foreground">Using the server default.</p>
        ) : (
          <button
            type="button"
            onClick={onClear}
            className="text-xs text-muted-foreground underline-offset-2 hover:underline"
          >
            Clear
          </button>
        )}
      </div>
    </div>
  );
}
