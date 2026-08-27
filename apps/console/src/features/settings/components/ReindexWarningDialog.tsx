import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";

/**
 * Shown before saving a change to one of the three embedding fields. The wording
 * says "may" on purpose: the signature is computed from the RESOLVED settings, so
 * clearing a field back to the env default can land on the same signature and not
 * re-embed at all. Promising a reindex that does not happen is as bad as the
 * reverse.
 */
export function ReindexWarningDialog({
  open,
  documentCount,
  onConfirm,
  onClose,
  isPending,
}: {
  open: boolean;
  documentCount: number;
  onConfirm: () => void;
  onClose: () => void;
  isPending: boolean;
}) {
  if (!open) return null;
  return (
    <Modal open onClose={onClose} title="This may re-embed your lore">
      <p className="text-sm text-muted-foreground">
        You changed a setting that defines the embedding space. If the new setting resolves to a
        different one, all {documentCount} document{documentCount === 1 ? "" : "s"} in this project
        are indexed again from scratch.
      </p>
      <p className="mt-2 text-sm text-muted-foreground">
        While that runs, NPCs in this project answer{" "}
        <strong>&ldquo;the lore is being re-embedded&rdquo;</strong> instead of talking. Nothing is
        lost, and you can watch the progress on the Lore tab.
      </p>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button variant="primary" disabled={isPending} onClick={onConfirm}>
          {isPending ? "Saving…" : "Save and re-embed"}
        </Button>
      </div>
    </Modal>
  );
}
