import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import type { Project } from "@/types/projects";

import { useRenameProject } from "../hooks";
import { ErrorState } from "@/components/ui/ErrorState";

export function RenameProjectDialog({
  project,
  open,
  onClose,
}: {
  project: Project;
  open: boolean;
  onClose: () => void;
}) {
  const [name, setName] = useState(project.name);
  const rename = useRenameProject();

  const close = () => {
    setName(project.name);
    rename.reset();
    onClose();
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await rename.mutateAsync({ id: project.id, name: name.trim() });
      close();
    } catch {
      // The mutation's own error state renders below. Rethrowing here would
      // only surface as an unhandled rejection.
    }
  };

  return (
    <Modal open={open} onClose={close} title="Rename project">
      <form onSubmit={submit} className="space-y-4">
        <Input
          autoFocus
          required
          maxLength={200}
          value={name}
          onChange={(event) => setName(event.target.value)}
        />

        {rename.error && <ErrorState error={rename.error} />}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={close}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={rename.isPending || !name.trim()}>
            {rename.isPending ? "Saving…" : "Rename"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
