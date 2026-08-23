import { Modal } from "@/components/ui/Modal";
import type { ApiKey } from "@/types/keys";

import { useRevokeKey } from "../hooks";

export function RevokeKeyDialog({
  apiKey,
  open,
  onClose,
}: {
  apiKey: ApiKey;
  open: boolean;
  onClose: () => void;
}) {
  const revoke = useRevokeKey();

  const submit = async () => {
    try {
      await revoke.mutateAsync(apiKey.id);
      revoke.reset();
      onClose();
    } catch {
      // The mutation's own error state renders below. Rethrowing here would
      // only surface as an unhandled rejection.
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Revoke this key">
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Anything using <strong>{apiKey.label ?? "this key"}</strong> stops working{" "}
          <strong>on its very next request</strong>, not after a cache expires — the revoke route
          clears the identity cache. If Mantella is pointed at a URL containing it, that
          conversation ends mid-sentence.
        </p>

        {revoke.error && <p className="text-sm text-destructive">{revoke.error.message}</p>}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-3 py-2 text-sm hover:bg-accent"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={revoke.isPending}
            className="rounded-md bg-destructive px-3 py-2 text-sm text-white disabled:opacity-50"
          >
            {revoke.isPending ? "Revoking…" : "Revoke key"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
