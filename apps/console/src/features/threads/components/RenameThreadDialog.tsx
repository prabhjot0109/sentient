import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
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
      <Input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} />
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button
          variant="primary"
          disabled={!title.trim() || isPending}
          onClick={() => onConfirm(title.trim())}
        >
          {isPending ? "Saving…" : "Save"}
        </Button>
      </div>
    </Modal>
  );
}
