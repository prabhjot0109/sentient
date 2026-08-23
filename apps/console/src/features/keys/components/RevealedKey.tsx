import { useState } from "react";

import { CopyButton } from "@/components/ui/CopyButton";
import { Modal } from "@/components/ui/Modal";
import type { CreatedApiKey } from "@/types/keys";

/**
 * The raw key exists here and nowhere else, ever again. generate_api_key()
 * returns (raw, sha256) and only the hash is stored, so GET /v1/keys cannot
 * return it and neither can support. This has to be unmistakable BEFORE the
 * user dismisses it, which is why the dismiss control is gated rather than
 * merely accompanied by a warning.
 */
export function RevealedKey({
  created,
  onDismiss,
}: {
  created: CreatedApiKey;
  onDismiss: () => void;
}) {
  const [acknowledged, setAcknowledged] = useState(false);

  return (
    <Modal open onClose={onDismiss} title="Copy this key now">
      <div className="space-y-4">
        <p className="text-sm text-destructive">
          This is the only time this key will be shown. Copy it now — it cannot be recovered, only
          replaced.
        </p>

        <code className="block rounded-md border border-border bg-muted p-3 font-mono text-xs break-all">
          {created.api_key}
        </code>

        <CopyButton
          value={created.api_key}
          label="Copy key"
          onCopied={() => setAcknowledged(true)}
        />

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={(event) => setAcknowledged(event.target.checked)}
          />
          I&rsquo;ve saved this key somewhere safe.
        </label>

        <div className="flex justify-end">
          <button
            type="button"
            disabled={!acknowledged}
            onClick={onDismiss}
            className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50"
          >
            Done
          </button>
        </div>
      </div>
    </Modal>
  );
}
