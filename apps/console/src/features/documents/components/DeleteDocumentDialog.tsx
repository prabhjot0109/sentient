import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import type { SourceDocument } from "@/types/documents";
import { ErrorState } from "@/components/ui/ErrorState";

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
  error: unknown;
}) {
  const [typed, setTyped] = useState("");
  if (!document) return null;

  return (
    <Modal open onClose={onClose} title="Delete this document?">
      <p className="text-sm text-muted-foreground">
        Its chunks leave the index immediately. NPCs stop being able to cite it. Type{" "}
        <code className="font-medium text-foreground">{document.filename}</code> to confirm.
      </p>
      <Input
        aria-label={`Type ${document.filename} to confirm`}
        autoFocus
        value={typed}
        onChange={(e) => setTyped(e.target.value)}
        className="mt-3"
      />
      {error != null && <ErrorState error={error} />}
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button
          variant="destructive"
          disabled={typed !== document.filename || isPending}
          onClick={() => onConfirm(document.filename)}
        >
          {isPending ? "Deleting…" : "Delete"}
        </Button>
      </div>
    </Modal>
  );
}
