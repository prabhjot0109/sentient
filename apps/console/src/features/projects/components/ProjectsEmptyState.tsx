import { NewProjectDialog } from "./NewProjectDialog";

/**
 * The first screen a new account sees, so it has to say what a project IS in
 * Sentient's terms rather than just offer a button.
 */
export function ProjectsEmptyState() {
  return (
    <div className="mx-auto max-w-lg space-y-4 p-8">
      <h1 className="text-xl font-semibold">Create your first project</h1>
      <p className="text-sm text-muted-foreground">
        A project is <strong>one game</strong>. It owns that game&rsquo;s lore, its persona and its
        conversations, which is what keeps Skyrim&rsquo;s lore out of Fallout&rsquo;s answers. Every
        NPC in one game shares the project&rsquo;s persona; there is no per-NPC setup.
      </p>
      <NewProjectDialog label="Create a project" />
    </div>
  );
}
