import { useState } from "react";

import { Modal } from "@/components/ui/Modal";
import { PROVIDERS } from "@/types/credentials";

export function AddCredentialDialog({
  existingProviders,
  onSubmit,
  isPending,
  error,
}: {
  existingProviders: string[];
  /**
   * Resolves when the key is stored, rejects when it is not.
   *
   * The F3+F4 plan passed a plain `onConfirm` and named the consequence as a gap
   * to close: with nothing coming back, the dialog cannot know the store
   * succeeded and stays open over a key it has already saved. A promise is the
   * smallest thing that carries that answer, and it keeps `open` inside the
   * dialog -- lifting it to a parent is what makes a shell component know what a
   * credential is.
   */
  onSubmit: (provider: string, apiKey: string) => Promise<unknown>;
  isPending: boolean;
  error: string | null;
}) {
  const [open, setOpen] = useState(false);
  const [provider, setProvider] = useState<string>(PROVIDERS[0]);
  const [apiKey, setApiKey] = useState("");

  const close = () => {
    setOpen(false);
    // Never leave a plaintext key sitting in state behind a closed dialog.
    setApiKey("");
  };

  const submit = () => {
    // The rejection is already rendered from the mutation's `error`; swallowing
    // it here only stops it becoming an unhandled rejection.
    onSubmit(provider, apiKey.trim()).then(close, () => {});
  };

  return (
    <>
      {/*
        The dialog owns its own trigger and its own state, so both the empty state
        and the toolbar can drop it in with nothing threaded through a parent.
      */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent"
      >
        Add a provider key
      </button>

      {open && (
        <Modal open onClose={close} title="Add a provider key">
          <p className="text-sm text-muted-foreground">
            Stored encrypted. It is never shown again, and never appears in a response or a log —
            only the last few characters are kept, so you can recognise it.
          </p>
          <label className="mt-3 block text-sm">
            Provider
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              {PROVIDERS.map((option) => (
                <option key={option} value={option}>
                  {option}
                  {existingProviders.includes(option) ? " (replaces the current key)" : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="mt-3 block text-sm">
            API key
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              autoComplete="off"
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </label>
          {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
          <div className="mt-4 flex justify-end gap-2">
            <button type="button" onClick={close} className="text-sm text-muted-foreground">
              Cancel
            </button>
            <button
              type="button"
              disabled={!apiKey.trim() || isPending}
              onClick={submit}
              className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
            >
              {isPending ? "Storing…" : "Store"}
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
