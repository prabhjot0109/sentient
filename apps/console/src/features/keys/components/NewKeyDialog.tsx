import { Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import type { CreatedApiKey } from "@/types/keys";

import { useCreateKey } from "../hooks";

/**
 * Hands the minted key UP rather than rendering it. The raw value has to reach
 * the Mantella card as well as the reveal, and this dialog is not the owner of
 * either.
 *
 * `atCap` closes the loop the backend opened. The POST answers 409 at
 * `MAX_API_KEYS_PER_USER` with a sentence naming the number, and that sentence is
 * now rendered correctly (it used to arrive as "Your lore is re-embedding" --
 * every 409 mapped to the reindex guard). But the better outcome is not reaching
 * it: the button says why it is disabled, so the failure is prevented rather than
 * explained afterwards. The 409 path is still live and still correct, because two
 * tabs can race past a client-side check.
 */
export function NewKeyDialog({
  onCreated,
  atCap = false,
  limit = 0,
}: {
  onCreated: (key: CreatedApiKey) => void;
  atCap?: boolean;
  limit?: number;
}) {
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
      <div className="flex flex-col items-end gap-1">
        <Button variant="primary" onClick={() => setOpen(true)} disabled={atCap}>
          <Plus className="size-4" />
          Create a key
        </Button>
        {atCap && (
          // Beside the control, not inside a toast. A disabled button with no
          // stated reason is the interaction users describe as "the button
          // doesn't work".
          <p className="text-xs text-warning">
            You have {limit} active keys, the maximum. Revoke one to make room.
          </p>
        )}
      </div>

      <Modal open={open} onClose={close} title="Create an API key">
        <form onSubmit={submit} className="space-y-4">
          <label className="block space-y-1">
            <span className="text-sm font-medium">Label (optional)</span>
            <Input
              autoFocus
              maxLength={100}
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
