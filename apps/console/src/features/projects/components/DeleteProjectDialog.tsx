import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import type { Project } from "@/types/projects";

import { useDeleteProject } from "../hooks";
import { ErrorState } from "@/components/ui/ErrorState";

/**
 * Typed confirmation, not a plain "Are you sure?". Every foreign key into a
 * project is ON DELETE CASCADE, so this takes the project's config, documents,
 * threads and every message in them. A user who thinks they are hiding a project
 * does not get it back.
 */
export function DeleteProjectDialog({
  project,
  open,
  onClose,
  onDeleted,
}: {
  project: Project;
  open: boolean;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [confirmation, setConfirmation] = useState("");
  const remove = useDeleteProject();

  const close = () => {
    setConfirmation("");
    remove.reset();
    onClose();
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await remove.mutateAsync(project.id);
      close();
      onDeleted();
    } catch {
      // The mutation's own error state renders below. Rethrowing here would
      // only surface as an unhandled rejection.
    }
  };

  return (
    <Modal open={open} onClose={close} title={`Delete ${project.name}`}>
      <form onSubmit={submit} className="space-y-4">
        <p className="text-sm text-muted-foreground">
          This deletes the project&rsquo;s settings, its persona, every document you have uploaded
          to it and every conversation held in it. It cannot be undone.
        </p>

        <label className="block space-y-1">
          <span className="text-sm">
            Type <strong className="font-mono">{project.name}</strong> to confirm.
          </span>
          <Input
            autoFocus
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
          />
        </label>

        {remove.error && <ErrorState error={remove.error} />}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={close}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="destructive"
            disabled={remove.isPending || confirmation !== project.name}
          >
            {remove.isPending ? "Deleting…" : "Delete project"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
