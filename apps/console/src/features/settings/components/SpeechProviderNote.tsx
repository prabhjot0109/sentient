import { useCredentials } from "@/features/credentials";

/** The only two providers that serve Whisper, in the order the resolver tries them. */
const WHISPER_PROVIDERS = ["groq", "openai"] as const;

/**
 * Which speech-to-text provider an in-game utterance will reach.
 *
 * This is a READ, not a control. Selection now EXISTS -- `STT_PROVIDER` and
 * `STT_BASE_URL` are in `core/config.py`, and `adapters/stt/client.PROVIDERS`
 * carries groq, openai and a custom OpenAI-compatible endpoint -- but it is
 * deployment-wide, not per project. There is still no `stt_*` column in
 * `project_configs`, so a per-project pane would have nothing to write to.
 * H9's remaining half is that column, a migration and a `ConfigInput` field.
 *
 * What this can honestly show is what `resolve_stt_credential` will pick, which
 * is partly derived from the vault -- one of the reasons F3 and F4 are one plan.
 *
 * The precedence, read off that function rather than assumed: a Whisper key
 * Mantella forwards wins outright; otherwise it walks Groq then OpenAI and, for
 * EACH provider, takes the user's stored key before that provider's env key. So
 * a stored OpenAI key does not beat the server's Groq key -- the loop is
 * per-provider, not stored-first-across-providers, and saying otherwise here
 * would be worse than saying nothing.
 */
export function SpeechProviderNote() {
  const { data: credentials, error } = useCredentials();

  // With no readable vault there is nothing this note can add beyond the fixed
  // precedence, and the vault screen already explains why. Say the general thing.
  const stored = new Set((credentials ?? []).map((c) => c.provider));

  return (
    <div className="space-y-2">
      <div>
        <h2 className="text-sm font-medium">Speech to text</h2>
        <p className="text-xs text-muted-foreground">
          Not a per-project setting — there is no column for one. This is what the server will
          resolve for an in-game utterance.
        </p>
      </div>
      <ul className="space-y-1 rounded-md border border-border p-3 text-sm text-muted-foreground">
        <li>1. A Whisper key Mantella forwards with the request, if it sends one.</li>
        {WHISPER_PROVIDERS.map((provider, index) => (
          <li key={provider}>
            {index + 2}. <span className="font-medium text-foreground">{provider}</span> —{" "}
            {error
              ? "your stored key, then the server's."
              : stored.has(provider)
                ? "your stored key."
                : "the server's own key, since you have none stored."}
          </li>
        ))}
      </ul>
    </div>
  );
}
