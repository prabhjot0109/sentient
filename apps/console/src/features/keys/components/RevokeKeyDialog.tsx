import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import type { ApiKey } from "@/types/keys";

import { useRevokeKey } from "../hooks";
import { ErrorState } from "@/components/ui/ErrorState";

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

        {revoke.error && <ErrorState error={revoke.error} />}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={submit} disabled={revoke.isPending}>
            {revoke.isPending ? "Revoking…" : "Revoke key"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
