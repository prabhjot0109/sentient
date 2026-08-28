import { Link } from "@tanstack/react-router";

import type { PersonaSource, ProjectDetail } from "@/types/projects";

/**
 * What this project's NPCs sound like, quoted, at the top of the surface where
 * you talk to one.
 *
 * The persona IS the product -- it is the single value that shapes every line an
 * NPC speaks -- and until now the console showed it as a grey paragraph under a
 * 14px "Persona" heading, indistinguishable from a description field.
 *
 * `persona_source` is the fact that makes this worth foregrounding rather than
 * merely styling. H1's Finding 4 measured a project whose STORED persona_prompt
 * was NULL while its NPCs visibly had a voice from the preset, so "no persona"
 * and "a persona you did not write" are different states and only the backend
 * can tell them apart. Nothing else in the console reports which one you are in.
 */
const SOURCE: Record<PersonaSource, string> = {
  custom: "you wrote this",
  preset: "from the preset",
  generic: "no persona set",
};

export function VoiceHero({ project }: { project: ProjectDetail }) {
  const model = project.config.model_name;
  const provider = project.config.llm_provider;

  return (
    <section className="mb-10">
      <p className="font-mono mb-3 text-[11px] tracking-[0.14em] text-muted-foreground uppercase">
        The voice
        <span className="mx-2 text-border">/</span>
        <span className={project.persona_source === "generic" ? "text-amber-500" : "text-brand"}>
          {SOURCE[project.persona_source]}
        </span>
      </p>

      {/*
        The one piece of large type on this page, in the display face. Clamped
        rather than scrolled: a persona can run to several paragraphs, and the
        hero's job is to tell you which voice is loaded, not to be the editor.
      */}
      <blockquote className="font-display line-clamp-4 text-xl leading-snug font-medium tracking-tight text-balance">
        {project.persona_prompt}
      </blockquote>

      <p className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
        {/*
          Provider and model are stored-or-null by design: null means "unset, so
          the server's default applies", which is not the same as a value the
          user chose. Saying so beats printing the word "null".
        */}
        <span className="font-mono">{model ?? "default model"}</span>
        {provider && <span className="font-mono text-border">· {provider}</span>}
        <span className="text-border">·</span>
        <Link
          to="/app/p/$pid/settings"
          params={{ pid: project.id }}
          className="underline underline-offset-4 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          Edit the voice
        </Link>
      </p>
    </section>
  );
}
