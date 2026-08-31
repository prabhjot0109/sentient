import { useState } from "react";

import { CopyButton } from "@/components/ui/CopyButton";
import { useProjects } from "@/features/projects";
import type { CreatedApiKey } from "@/types/keys";

const API_ORIGIN = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

/**
 * Whether the base URL points back at the operator's own machine.
 *
 * The `127.0.0.1`-not-`localhost` advice below is specific to that case: it is a
 * Windows loopback resolution cost, not a general rule about URLs. Printing it
 * beside a deployed `https://` origin tells a hosted user to edit a hostname that
 * is not in their URL, so the note is hidden unless it applies.
 */
const API_IS_LOOPBACK = /^https?:\/\/(127\.0\.0\.1|localhost|\[::1\])(:|\/|$)/.test(API_ORIGIN);

const PLACEHOLDER = "<your-api-key>";

/** Enough of the key to recognise, not enough to use. */
const mask = (key: string) => `${key.slice(0, 12)}…${key.slice(-4)}`;

/**
 * The payoff. Not the key -- the copy-paste base URL, which is what makes
 * Sentient usable from the game without curl.
 *
 * The project is picked here rather than passed down from the route. Keys are
 * scoped to the USER and projects are scoped to the user; the Mantella URL is
 * their cross product. Routing this screen under a project would nest keys
 * inside something that does not own them.
 */
export function MantellaSetupCard({ created }: { created: CreatedApiKey | null }) {
  const { data: projects } = useProjects();
  const [pickedId, setPickedId] = useState<string | null>(null);

  // Resolved against the live list, not trusted from state: a project deleted in
  // another tab would otherwise leave the picker blank and the URL pointing at a
  // project that no longer exists.
  const projectId =
    projects?.find((project) => project.id === pickedId)?.id ?? projects?.[0]?.id ?? null;
  const key = created?.api_key ?? null;

  // What goes on screen and what goes on the clipboard differ ON PURPOSE. The
  // reveal dialog is the one-time warning; after it is dismissed the URL stays
  // useful without leaving key material sitting on the page. Reconstructing this
  // from a LISTED key is impossible -- list_api_keys returns no key material at
  // all -- so a masked value pasted into Mantella would fail looking like a
  // server fault. Hence the copy button carries the real one.
  const shown = `${API_ORIGIN}/v1/${key ? mask(key) : PLACEHOLDER}/${projectId ?? "<project-id>"}`;
  const real = key && projectId ? `${API_ORIGIN}/v1/${key}/${projectId}` : null;

  return (
    <section className="space-y-5 rounded-xl border border-border bg-card p-5 sm:p-6">
      <div className="space-y-1">
        <h2 className="text-base font-semibold">Point Mantella at this project</h2>
        <p className="max-w-prose text-sm text-muted-foreground">
          The key and the project are both in the URL, because Mantella cannot send request headers.
          That is why this looks unlike a normal API base URL.
        </p>
      </div>

      {projects && projects.length > 1 && (
        <label className="block max-w-xs space-y-1">
          <span className="text-sm font-medium">Project</span>
          <select
            value={projectId ?? ""}
            onChange={(event) => setPickedId(event.target.value)}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
      )}

      <div className="space-y-2">
        <code className="block rounded-lg border border-border bg-muted p-3 font-mono text-xs break-all">
          {shown}
        </code>

        {real ? (
          <CopyButton value={real} label="Copy the full URL" />
        ) : (
          <p className="text-sm text-muted-foreground">
            {projects?.length
              ? "The masked key above is a placeholder. Create a key and the full, copyable URL appears here — it is shown once, in this tab, and cannot be rebuilt from a key you already made."
              : "Create a project first — the URL names the project whose lore the NPC is grounded in."}
          </p>
        )}
      </div>

      <div className="space-y-3 border-t border-border pt-5 text-sm">
        <p className="font-medium">Setup</p>
        <ol className="space-y-2 text-muted-foreground">
          {[
            "In Mantella, set the LLM service to a custom OpenAI-compatible endpoint.",
            "Paste this base URL.",
            "Leave Mantella's own API-key field blank, or set it to anything. The key is already in the URL.",
            "Upload your lore to this project. The NPC is grounded only in the lore of the project named in that URL.",
          ].map((step, index) => (
            // A numbered SEQUENCE, which these genuinely are -- the order carries
            // information, since step 2 cannot be done before step 1. Not the
            // decorative "01 / 02 / 03" markers that get scattered above unordered
            // sections.
            <li key={step} className="flex gap-3">
              <span
                aria-hidden
                className="font-mono mt-px grid size-5 shrink-0 place-items-center rounded-full border border-border text-[11px] text-foreground"
              >
                {index + 1}
              </span>
              <span className="flex-1">{step}</span>
            </li>
          ))}
        </ol>
        {API_IS_LOOPBACK && (
          <p className="rounded-lg bg-muted p-3 text-muted-foreground">
            <strong className="text-foreground">
              Use <code>127.0.0.1</code>, not <code>localhost</code>.
            </strong>{" "}
            Uvicorn binds IPv4 only, and Windows resolves <code>localhost</code> to <code>::1</code>{" "}
            first — a measured 208 ms of wasted connect time on every single request, which does not
            show up in the server&rsquo;s own logs.
          </p>
        )}
      </div>
    </section>
  );
}
