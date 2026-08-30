import type { Utterance } from "@/types/voice";

import { Badge } from "@/components/ui/Badge";
import { ErrorState } from "@/components/ui/ErrorState";
import { useRecentUtterances } from "../hooks";
import { explain, levelFraction, toneOf } from "../verdict";

function Level({ utterance }: { utterance: Utterance }) {
  const { rms_pct, peak_pct, clipped_pct } = utterance.audio;
  return (
    <div className="flex items-center gap-2">
      <div
        className="h-1.5 w-24 overflow-hidden rounded-full bg-muted"
        role="img"
        aria-label={`Input level ${rms_pct.toFixed(1)} percent`}
      >
        <div
          className={`h-full rounded-full ${clipped_pct > 1 ? "bg-warning" : "bg-foreground/40"}`}
          style={{ width: `${levelFraction(rms_pct) * 100}%` }}
        />
      </div>
      {/* Tabular figures so the numbers form a column instead of jittering
          between rows, which is what makes a quiet capture stand out. */}
      <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
        {rms_pct.toFixed(1)}% / {peak_pct.toFixed(0)}%
      </span>
    </div>
  );
}

function Row({ utterance }: { utterance: Utterance }) {
  const note = explain(utterance);
  return (
    <li className="space-y-1.5 border-t border-border py-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] text-muted-foreground">{utterance.time}</span>
        <Badge tone={toneOf(utterance)}>{utterance.audio.verdict}</Badge>
        <Level utterance={utterance} />
      </div>
      <p className={utterance.text ? "text-sm" : "text-sm text-muted-foreground italic"}>
        {utterance.text || "nothing heard"}
      </p>
      {note && <p className="text-xs text-muted-foreground">{note}</p>}
      <p className="text-[11px] text-muted-foreground">
        {utterance.provider} · {utterance.model}
        {utterance.audio.duration_s > 0 && ` · ${utterance.audio.duration_s.toFixed(1)}s captured`}
        {utterance.elapsed_s !== undefined && ` · ${utterance.elapsed_s.toFixed(2)}s upstream`}
      </p>
    </li>
  );
}

/**
 * What the microphone actually sent, and what came back.
 *
 * The one screen for the question a transcript alone cannot answer: an empty
 * result looks identical whether the mic was dead, the level was too low, or the
 * model heard nothing in perfectly good audio -- and those need opposite fixes.
 * The measurements were already being taken on every utterance and printed to
 * the server log; this is the same data with the log removed as a prerequisite.
 *
 * Server-side this buffer is in-memory, per user, and capped at 50, so it is
 * empty after a restart. Said plainly in the empty state rather than left to
 * look like a bug.
 */
export function MicHistory() {
  const { data, error, isPending } = useRecentUtterances();

  return (
    <div className="space-y-2">
      <div>
        <h2 className="text-sm font-medium">Recent microphone input</h2>
        <p className="text-xs text-muted-foreground">
          Every utterance from this console and from Mantella, with the levels measured on arrival.
          Held in memory only — cleared when the server restarts.
        </p>
      </div>

      {error ? (
        <ErrorState error={error} />
      ) : isPending ? (
        <p className="rounded-md border border-border p-3 text-sm text-muted-foreground">
          Loading…
        </p>
      ) : data.transcriptions.length === 0 ? (
        <p className="rounded-md border border-border p-3 text-sm text-muted-foreground">
          Nothing yet. Hold the mic in a chat, or point Mantella&rsquo;s Whisper URL at this server.
          In-game utterances only appear here if Mantella sends your Sentient API key.
        </p>
      ) : (
        <div className="rounded-md border border-border p-3">
          <p className="pb-2 text-xs text-muted-foreground">
            {data.count} recent · {data.empty_transcriptions} produced no text
          </p>
          <ul>
            {data.transcriptions.map((utterance, index) => (
              // The buffer has no id and can hold two identical lines a second
              // apart, so index is the only stable key available. It is safe
              // here: the list is replaced wholesale on every refetch and never
              // reordered or spliced.
              <Row key={index} utterance={utterance} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
