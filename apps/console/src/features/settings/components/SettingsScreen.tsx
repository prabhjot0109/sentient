import { useState } from "react";

import { useDocuments } from "@/features/documents";
import { useProject } from "@/features/projects";
import { MicHistory } from "@/features/voice";
import { ErrorState } from "@/components/ui/ErrorState";
import type { ConfigPatch } from "@/lib/api/config";

import { useSetPersona, useUpdateConfig } from "../hooks";
import { willReindex } from "../reindex";
import { ConfigForm } from "./ConfigForm";
import { PersonaEditor } from "./PersonaEditor";
import { ReindexWarningDialog } from "./ReindexWarningDialog";
import { SpeechProviderNote } from "./SpeechProviderNote";

export function SettingsScreen({ projectId }: { projectId: string }) {
  const { data: project, error, isPending } = useProject(projectId);
  const { data: documents = [] } = useDocuments(projectId);
  const updateConfig = useUpdateConfig(projectId);
  const setPersona = useSetPersona(projectId);
  const [confirming, setConfirming] = useState<ConfigPatch | null>(null);

  if (isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;
  // describe() already distinguishes the 404 from everything else, so the
  // hand-rolled branch this used to carry is one line now.
  if (error || !project) return <ErrorState error={error} />;

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
        error={setPersona.error}
      />

      <ConfigForm
        config={project.config}
        savedAt={updateConfig.data?.updated_at ?? null}
        onSave={save}
        isSaving={updateConfig.isPending}
        error={updateConfig.error}
      />

      <SpeechProviderNote />

      {/* Directly under the provider note, because the two answer halves of one
          question: which service will hear you, and what it heard last. Both are
          deployment-wide rather than per project, so they read oddly on a
          project settings page in isolation and sensibly as a pair. */}
      <MicHistory />

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
