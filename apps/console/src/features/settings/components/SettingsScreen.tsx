import { useState } from "react";

import { useDocuments } from "@/features/documents";
import { useProject } from "@/features/projects";
import type { ConfigPatch } from "@/lib/api/config";
import { ApiError, NotFoundError } from "@/lib/api/errors";

import { useSetPersona, useUpdateConfig } from "../hooks";
import { willReindex } from "../reindex";
import { ConfigForm } from "./ConfigForm";
import { PersonaEditor } from "./PersonaEditor";
import { ReindexWarningDialog } from "./ReindexWarningDialog";
import { SpeechProviderNote } from "./SpeechProviderNote";

const message = (error: unknown): string | null =>
  error instanceof ApiError ? error.detail : error ? "Something went wrong." : null;

export function SettingsScreen({ projectId }: { projectId: string }) {
  const { data: project, error, isPending } = useProject(projectId);
  const { data: documents = [] } = useDocuments(projectId);
  const updateConfig = useUpdateConfig(projectId);
  const setPersona = useSetPersona(projectId);
  const [confirming, setConfirming] = useState<ConfigPatch | null>(null);

  if (isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (error instanceof NotFoundError) {
    return (
      <p className="text-sm text-muted-foreground">
        This project has been deleted, or it belongs to another account.
      </p>
    );
  }
  if (error || !project) {
    return <p className="text-sm text-destructive">{message(error) ?? "Project unavailable."}</p>;
  }

  const save = (patch: ConfigPatch) => {
    if (willReindex(patch, project.config)) setConfirming(patch);
    else updateConfig.mutate(patch);
  };

  return (
    <div className="max-w-3xl space-y-8">
      <PersonaEditor
        personaPrompt={project.persona_prompt}
        personaSource={project.persona_source}
        onSave={(prompt) => setPersona.mutate(prompt)}
        isSaving={setPersona.isPending}
        error={message(setPersona.error)}
      />

      <ConfigForm
        config={project.config}
        savedAt={updateConfig.data?.updated_at ?? null}
        onSave={save}
        isSaving={updateConfig.isPending}
        error={message(updateConfig.error)}
      />

      <SpeechProviderNote />

      <ReindexWarningDialog
        open={confirming !== null}
        documentCount={documents.length}
        isPending={updateConfig.isPending}
        onClose={() => setConfirming(null)}
        onConfirm={() => {
          if (confirming) updateConfig.mutate(confirming, { onSuccess: () => setConfirming(null) });
        }}
      />
    </div>
  );
}
