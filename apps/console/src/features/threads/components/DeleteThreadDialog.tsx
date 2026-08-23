import { Modal } from "@/components/ui/Modal";
import type { Thread } from "@/types/threads";

/**
 * No typed-name confirmation, unlike `DeleteProjectDialog` and
 * `DeleteDocumentDialog`. A conversation is cheaper to lose than a project,
 * which takes its documents and every thread with it; the typed gate is priced
 * for that, not for this.
 */
export function DeleteThreadDialog({
  thread,
  onConfirm,
  onClose,
  isPending,
}: {
  thread: Thread | null;
  onConfirm: () => void;
  onClose: () => void;
  isPending: boolean;
}) {
  if (!thread) return null;
  return (
    <Modal open onClose={onClose} title="Delete this conversation?">
      <p className="text-sm text-muted-foreground">
        “{thread.title || "Untitled conversation"}” and every message in it are removed. If this is
        an in-game conversation, the NPC loses that memory.
      </p>
      <div className="mt-4 flex justify-end gap-2">
        <button type="button" onClick={onClose} className="text-sm text-muted-foreground">
          Cancel
        </button>
        <button
          type="button"
          disabled={isPending}
          onClick={onConfirm}
          className="rounded-md bg-destructive px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {isPending ? "Deleting…" : "Delete"}
        </button>
      </div>
    </Modal>
  );
}
