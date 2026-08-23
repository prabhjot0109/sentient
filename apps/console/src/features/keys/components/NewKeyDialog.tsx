import { useState } from "react";

import { Modal } from "@/components/ui/Modal";
import type { CreatedApiKey } from "@/types/keys";

import { useCreateKey } from "../hooks";

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
    const key = await create.mutateAsync(label.trim() || null);
    close();
    onCreated(key);
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground"
      >
        Create a key
      </button>

      <Modal open={open} onClose={close} title="Create an API key">
        <form onSubmit={submit} className="space-y-4">
          <label className="block space-y-1">
            <span className="text-sm font-medium">Label (optional)</span>
            <input
              autoFocus
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder="my gaming PC"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
            <span className="block text-xs text-muted-foreground">
              The label is the only way to tell two keys apart later. The key itself is never shown
              again.
            </span>
          </label>

          {create.error && <p className="text-sm text-destructive">{create.error.message}</p>}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={close}
              className="rounded-md px-3 py-2 text-sm hover:bg-accent"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={create.isPending}
              className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50"
            >
              {create.isPending ? "Creating…" : "Create key"}
            </button>
          </div>
        </form>
      </Modal>
    </>
  );
}
