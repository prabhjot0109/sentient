import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
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
  const toast = useToast();

  const submit = async () => {
    try {
      await revoke.mutateAsync(apiKey.id);
      revoke.reset();
      onClose();
      // The row does not disappear -- it moves into the collapsed "revoked"
      // group, which may well be closed. Without this the dialog simply shuts and
      // nothing visibly happens, which is indistinguishable from a failure.
      toast({
        tone: "success",
        title: "Key revoked",
        body: `${apiKey.label ?? "The key"} stops working on its next request.`,
      });
    } catch {
      // The mutation's own error state renders below. Rethrowing here would
      // only surface as an unhandled rejection.
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Revoke this key">
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Anything using <strong className="text-foreground">{apiKey.label ?? "this key"}</strong>{" "}
          stops working <strong className="text-foreground">on its very next request</strong>, not
          after a cache expires — the revoke route clears the identity cache. If Mantella is pointed
          at a URL containing it, that conversation ends mid-sentence.
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
