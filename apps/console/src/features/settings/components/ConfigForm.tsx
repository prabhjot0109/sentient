import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import type { ConfigPatch, WritableConfigField } from "@/lib/api/config";
import { PROVIDERS, SEARCH_TYPES } from "@/types/credentials";
import type { ProjectConfig } from "@/types/projects";

import { ConfigField } from "./ConfigField";
import { ErrorState } from "@/components/ui/ErrorState";

type FieldSpec = {
  key: WritableConfigField;
  label: string;
  hint?: string;
  kind: "text" | "number" | "provider" | "searchType";
  /** Mirrors the server-side bound, so a 422 is the second line of defence. */
  min?: number;
  max?: number;
  step?: number;
};

/**
 * Mirrors `ConfigInput` in `src/sentient/api/schemas/projects.py`, bounds
 * included. The bounds are duplicated here on purpose: the server's 422 is the
 * authority, but discovering it by submitting is a bad way to learn that
 * temperature stops at 2.
 *
 * `embedding_signature` is on `ProjectConfig` but cannot appear here -- it is
 * derived and read-only, `ConfigInput` forbids extra fields, and
 * `WritableConfigField` excludes it, so adding a row for it is a compile error
 * rather than a 422.
 */
const FIELDS: FieldSpec[] = [
  { key: "llm_provider", label: "LLM provider", kind: "provider" },
  { key: "model_name", label: "Model", kind: "text", hint: "e.g. openai/gpt-oss-20b" },
  { key: "temperature", label: "Temperature", kind: "number", min: 0, max: 2, step: 0.1 },
  { key: "max_tokens", label: "Max tokens", kind: "number", min: 1 },
  { key: "reasoning_effort", label: "Reasoning effort", kind: "text" },
  { key: "reasoning_format", label: "Reasoning format", kind: "text" },
  {
    key: "history_window",
    label: "History window",
    kind: "number",
    min: 1,
    hint: "Messages replayed into each turn",
  },

  {
    key: "embedding_provider",
    label: "Embedding provider",
    kind: "provider",
    hint: "Changing this re-embeds every document",
  },
  {
    key: "embedding_model_name",
    label: "Embedding model",
    kind: "text",
    hint: "Changing this re-embeds every document",
  },
  {
    key: "mrl_vector_size",
    label: "Vector size",
    kind: "number",
    min: 1,
    hint: "Changing this re-embeds every document",
  },

  { key: "rag_search_type", label: "Search type", kind: "searchType" },
  { key: "rag_top_k", label: "Top K", kind: "number", min: 1 },
  { key: "rag_fetch_k", label: "Fetch K", kind: "number", min: 1 },
  { key: "rag_mmr_lambda", label: "MMR lambda", kind: "number", min: 0, max: 1, step: 0.05 },
  {
    key: "rag_score_threshold",
    label: "Score threshold",
    kind: "number",
    min: 0,
    max: 1,
    step: 0.01,
  },
  { key: "rag_chunk_size", label: "Chunk size", kind: "number", min: 1 },
  { key: "rag_chunk_overlap", label: "Chunk overlap", kind: "number", min: 0 },
];

export function ConfigForm({
  config,
  savedAt,
  onSave,
  isSaving,
  error,
}: {
  config: ProjectConfig;
  /**
   * `updated_at` from the last successful config PUT, or null before one.
   *
   * The form has to forget its local patch once the server has taken it --
   * otherwise Save stays enabled over an identical row and `willReindex` keeps
   * warning about an embedding field that is no longer changing. This is the
   * signal for that, and it is a value that already moves on every write rather
   * than a flag or a clock: the same reasoning as `features/threads/transcript.ts`.
   */
  savedAt: string | null;
  onSave: (patch: ConfigPatch) => void;
  isSaving: boolean;
  error: unknown;
}) {
  // Only what the user touched. Sending the whole row would make every save look
  // like a change to the three embedding fields and warn every time.
  const [patch, setPatch] = useState<ConfigPatch>({});

  useEffect(() => setPatch({}), [savedAt]);

  const valueOf = (key: WritableConfigField) =>
    key in patch ? (patch[key] ?? null) : (config[key] ?? null);

  const set = (key: WritableConfigField, raw: string, kind: FieldSpec["kind"]) => {
    // "" is how a cleared input arrives, and it is also what a number input gives
    // for text the browser cannot parse. Both mean "unset", which is a null the
    // server stores -- not an empty string, which would be a value.
    const value = raw === "" ? null : kind === "number" ? Number(raw) : raw;
    setPatch((p) => ({ ...p, [key]: value }));
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSave(patch);
      }}
      className="space-y-3"
    >
      <div>
        <h2 className="text-sm font-medium">Model and retrieval</h2>
        <p className="text-xs text-muted-foreground">
          Every field left empty falls through to the server&rsquo;s own setting.
        </p>
      </div>

      <div className="rounded-md border border-border px-4">
        {FIELDS.map((field) => {
          const value = valueOf(field.key);
          return (
            <ConfigField
              key={field.key}
              label={field.label}
              hint={field.hint}
              value={value}
              onClear={() => setPatch((p) => ({ ...p, [field.key]: null }))}
            >
              {field.kind === "provider" || field.kind === "searchType" ? (
                <select
                  aria-label={field.label}
                  value={(value as string) ?? ""}
                  onChange={(e) => set(field.key, e.target.value, field.kind)}
                  className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm"
                >
                  <option value="">Server default</option>
                  {(field.kind === "provider" ? PROVIDERS : SEARCH_TYPES).map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              ) : (
                <Input
                  aria-label={field.label}
                  type={field.kind === "number" ? "number" : "text"}
                  value={value ?? ""}
                  min={field.min}
                  max={field.max}
                  step={field.step}
                  placeholder="Server default"
                  onChange={(e) => set(field.key, e.target.value, field.kind)}
                  className="py-1.5"
                />
              )}
            </ConfigField>
          );
        })}
      </div>

      {error != null && <ErrorState error={error} />}

      <Button
        type="submit"
        variant="primary"
        disabled={isSaving || Object.keys(patch).length === 0}
      >
        {isSaving ? "Saving…" : "Save changes"}
      </Button>
    </form>
  );
}
