import { useEffect, useState } from "react";

import { Modal } from "@/components/ui/Modal";
import type { Thread } from "@/types/threads";

export function RenameThreadDialog({
  thread,
  onConfirm,
  onClose,
  isPending,
}: {
  thread: Thread | null;
  onConfirm: (title: string) => void;
  onClose: () => void;
  isPending: boolean;
}) {
  const [title, setTitle] = useState("");
  // Prefill when a DIFFERENT thread opens the dialog. Without this the input
  // keeps the previous thread's title -- and a game thread's title is null, so
  // the field would show the last console thread's name over an in-game one.
  useEffect(() => setTitle(thread?.title ?? ""), [thread]);
  if (!thread) return null;

  return (
    <Modal open onClose={onClose} title="Rename conversation">
      <input
        autoFocus
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
      />
      <div className="mt-4 flex justify-end gap-2">
        <button type="button" onClick={onClose} className="text-sm text-muted-foreground">
          Cancel
        </button>
        <button
          type="button"
          disabled={!title.trim() || isPending}
          onClick={() => onConfirm(title.trim())}
          className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
        >
          {isPending ? "Saving…" : "Save"}
        </button>
      </div>
    </Modal>
  );
}
