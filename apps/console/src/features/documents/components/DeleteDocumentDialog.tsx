import { useState } from "react";

import { Modal } from "@/components/ui/Modal";
import type { SourceDocument } from "@/types/documents";

/**
 * Typed-name confirmation, matching `DeleteProjectDialog`.
 *
 * The typed text is deliberately NOT reset here. The caller remounts this on
 * every open and close by keying it on the document, which resets the field on
 * all four exits -- cancel, Escape, backdrop and a successful delete -- where an
 * internal reset would miss the last one and show the previous file's text.
 */
export function DeleteDocumentDialog({
  document,
  onConfirm,
  onClose,
  isPending,
  error,
}: {
  document: SourceDocument | null;
  onConfirm: (filename: string) => void;
  onClose: () => void;
  isPending: boolean;
  error: string | null;
}) {
  const [typed, setTyped] = useState("");
  if (!document) return null;

  return (
    <Modal open onClose={onClose} title="Delete this document?">
      <p className="text-sm text-muted-foreground">
        Its chunks leave the index immediately. NPCs stop being able to cite it. Type{" "}
        <code className="font-medium text-foreground">{document.filename}</code> to confirm.
      </p>
      <input
        autoFocus
        value={typed}
        onChange={(e) => setTyped(e.target.value)}
        className="mt-3 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
      />
      {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
      <div className="mt-4 flex justify-end gap-2">
        <button type="button" onClick={onClose} className="text-sm text-muted-foreground">
          Cancel
        </button>
        <button
          type="button"
          disabled={typed !== document.filename || isPending}
          onClick={() => onConfirm(document.filename)}
          className="rounded-md bg-destructive px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {isPending ? "Deleting…" : "Delete"}
        </button>
      </div>
    </Modal>
  );
}
