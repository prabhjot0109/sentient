import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import { Modal } from "@/components/ui/Modal";

import { useCreateProject, usePresets } from "../hooks";

/**
 * Renders its own trigger and owns its own open state. The rail and the first-run
 * screen both need to open this, and colocating the state here is what stops it
 * being threaded through the sidebar and the route just to reach two buttons.
 */
export function NewProjectDialog({ label = "New project", className = "" }) {
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
    const project = await create.mutateAsync({ name: name.trim(), basePreset });
    close();
    navigate({ to: "/app/p/$pid", params: { pid: project.id } });
  };

  return (
    <>
      <button type="button" className={className} onClick={() => setOpen(true)}>
        {label}
      </button>

      <Modal open={open} onClose={close} title="New project">
        <form onSubmit={submit} className="space-y-4">
          <label className="block space-y-1">
            <span className="text-sm font-medium">Name</span>
            <input
              autoFocus
              required
              maxLength={200}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Skyrim"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
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

          {create.error && <p className="text-sm text-destructive">{create.error.message}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={close}
              className="rounded-md px-3 py-2 text-sm hover:bg-accent"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={create.isPending || !name.trim()}
              className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50"
            >
              {create.isPending ? "Creating…" : "Create project"}
            </button>
          </div>
        </form>
      </Modal>
    </>
  );
}
