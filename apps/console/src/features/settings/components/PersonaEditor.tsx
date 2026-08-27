import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import type { PersonaSource } from "@/types/projects";
import { ErrorState } from "@/components/ui/ErrorState";

const SOURCE_NOTE: Record<PersonaSource, string> = {
  custom: "This project has its own persona.",
  preset: "Inherited from the preset. Saving here overrides it for this project.",
  generic: "No persona is set anywhere. NPCs answer without an in-world voice.",
};

/**
 * Renders the RESOLVED persona, not the stored one.
 *
 * H1's Finding 4 measured a project whose stored `persona_prompt` was NULL while
 * the NPC visibly had a persona from its preset, and it reproduces exactly:
 * measured again 2026-08-24 on a fresh `skyrim` project, `persona_source` was
 * `preset`, `persona_prompt` was a full in-world prompt, and `config.persona_prompt`
 * was `null`. An editor showing the stored value alone renders a blank box over a
 * live voice -- and saving that blank overwrites it. So the content is
 * `project.persona_prompt` (resolved) and `persona_source` is shown beside it,
 * because "editing my own" and "overriding an inherited one" are different acts.
 */
export function PersonaEditor({
  personaPrompt,
  personaSource,
  onSave,
  isSaving,
  error,
}: {
  personaPrompt: string;
  personaSource: PersonaSource;
  onSave: (prompt: string) => void;
  isSaving: boolean;
  error: unknown;
}) {
  const [text, setText] = useState(personaPrompt);
  // Re-seed when the server's value changes (a save, or switching project).
  useEffect(() => setText(personaPrompt), [personaPrompt]);

  return (
    <div className="space-y-2">
      <div>
        <h2 className="text-sm font-medium">Persona</h2>
        <p className="text-xs text-muted-foreground">
          One voice per project, not per NPC. {SOURCE_NOTE[personaSource]}
        </p>
      </div>
      <textarea
        aria-label="Persona"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={8}
        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
      />
      {error != null && <ErrorState error={error} />}
      <Button
        variant="primary"
        onClick={() => onSave(text)}
        // An empty prompt is a 422 (`system_prompt` is a required str, confirmed:
        // `{}` answers "Field required"), and text identical to the resolved value
        // would only convert an inherited persona into the same custom one.
        disabled={isSaving || !text.trim() || text === personaPrompt}
      >
        {isSaving ? "Saving…" : "Save persona"}
      </Button>
    </div>
  );
}
