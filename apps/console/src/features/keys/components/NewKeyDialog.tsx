import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import type { CreatedApiKey } from "@/types/keys";

import { useCreateKey } from "../hooks";
import { ErrorState } from "@/components/ui/ErrorState";

/**
 * Hands the minted key UP rather than rendering it. The raw value has to reach
 * the Mantella card as well as the reveal, and this dialog is not the owner of
 * either.
 */
export function NewKeyDialog({ onCreated }: { onCreated: (key: CreatedApiKey) => void }) {
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState("");
  const create = useCreateKey();

  const close = () => {
    setOpen(false);
    setLabel("");
    create.reset();
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      const key = await create.mutateAsync(label.trim() || null);
      close();
      onCreated(key);
    } catch {
      // The mutation's own error state renders below. Rethrowing here would
      // only surface as an unhandled rejection.
    }
  };

  return (
    <>
      <Button variant="primary" onClick={() => setOpen(true)}>
        Create a key
      </Button>

      <Modal open={open} onClose={close} title="Create an API key">
        <form onSubmit={submit} className="space-y-4">
          <label className="block space-y-1">
            <span className="text-sm font-medium">Label (optional)</span>
            <Input
              autoFocus
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder="my gaming PC"
            />
            <span className="block text-xs text-muted-foreground">
              The label is the only way to tell two keys apart later. The key itself is never shown
              again.
            </span>
          </label>

          {create.error && <ErrorState error={create.error} />}

          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={close}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={create.isPending}>
              {create.isPending ? "Creating…" : "Create key"}
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
