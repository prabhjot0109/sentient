import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";

import { useCreateProject, usePresets } from "../hooks";
import { ErrorState } from "@/components/ui/ErrorState";

/**
 * Renders its own trigger and owns its own open state. The rail and the first-run
 * screen both need to open this, and colocating the state here is what stops it
 * being threaded through the sidebar and the route just to reach two buttons.
 */
export function NewProjectDialog({
  label = "New project",
  variant = "primary",
  size = "md",
  className,
}: {
  label?: string;
  variant?: "primary" | "secondary" | "ghost" | "destructive";
  size?: "sm" | "md";
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [basePreset, setBasePreset] = useState("custom");
  const { data: presets } = usePresets();
  const create = useCreateProject();
  const navigate = useNavigate();

  const close = () => {
    setOpen(false);
    setName("");
    setBasePreset("custom");
    create.reset();
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      const project = await create.mutateAsync({ name: name.trim(), basePreset });
      close();
      navigate({ to: "/app/p/$pid", params: { pid: project.id } });
    } catch {
      // The mutation's own error state renders below. Rethrowing here would
      // only surface as an unhandled rejection.
    }
  };

  return (
    <>
      <Button variant={variant} size={size} className={className} onClick={() => setOpen(true)}>
        {label}
      </Button>

      <Modal open={open} onClose={close} title="New project">
        <form onSubmit={submit} className="space-y-4">
          <label className="block space-y-1">
            <span className="text-sm font-medium">Name</span>
            <Input
              autoFocus
              required
              maxLength={200}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Skyrim"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-sm font-medium">Preset</span>
            <select
              value={basePreset}
              onChange={(event) => setBasePreset(event.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="custom">custom</option>
              {presets?.map((preset) => (
                <option key={preset} value={preset}>
                  {preset}
                </option>
              ))}
            </select>
            <span className="block text-xs text-muted-foreground">
              A preset seeds the persona every NPC in this project speaks with. Pick{" "}
              <code>custom</code> for no preset persona; you can write your own later.
            </span>
          </label>

          {create.error && <ErrorState error={create.error} />}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={close}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={create.isPending || !name.trim()}>
              {create.isPending ? "Creating…" : "Create project"}
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
