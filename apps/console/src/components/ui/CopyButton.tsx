import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { Button } from "./Button";

/**
 * navigator.clipboard requires a secure context. localhost qualifies and so does
 * https, but it still rejects behind some permission policies, so the failure
 * path is real and says what to do instead. A copy button that silently does
 * nothing is worse than no button when the thing being copied cannot be
 * recovered.
 */
export function CopyButton({
  value,
  label = "Copy",
  onCopied,
  className,
}: {
  value: string;
  label?: string;
  onCopied?: () => void;
  className?: string;
}) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setState("copied");
      onCopied?.();
    } catch {
      setState("failed");
    }
  };

  return (
    <span className="inline-flex items-center gap-2">
      <Button size="sm" onClick={copy} className={className}>
        {state === "copied" ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
        {state === "copied" ? "Copied" : label}
      </Button>
      {state === "failed" && (
        <span className="text-xs text-destructive">
          Clipboard blocked — select the text above and copy it by hand.
        </span>
      )}
    </span>
  );
}
