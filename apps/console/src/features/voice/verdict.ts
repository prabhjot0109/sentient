import type { Utterance } from "@/types/voice";

export type Tone = "success" | "warning" | "danger";

/**
 * Verdicts the waveform reader can return that mean "this audio could plausibly
 * hold speech". Everything else explains an empty transcription by itself.
 *
 * Mirrors `AudioReport.speech_plausible`, minus UNREADABLE: on the server that
 * verdict counts as plausible so a decoder it cannot parse never blocks a
 * transcription, but for a READER it is a problem worth seeing -- the console
 * only ever uploads 16 kHz mono PCM, so UNREADABLE here means something is wrong
 * with the capture path rather than with the microphone.
 */
const HEALTHY = new Set(["OK", "HOT"]);

/**
 * How an utterance should read at a glance.
 *
 * `danger` is reserved for an upstream failure, matching how the `failed`
 * document pill already uses it. Note that `bg-destructive/10 text-destructive`
 * is the combination `tokens.css` records as a KNOWN GAP at 3.64:1 in dark mode;
 * it is used here for consistency with that existing pill rather than to add a
 * second, differently-coloured failure state. Audio problems take `warning`,
 * which is measured at 5.48:1 on its own tint -- so the common case is the
 * accessible one.
 */
export function toneOf(utterance: Utterance): Tone {
  if (utterance.error) return "danger";
  return HEALTHY.has(utterance.audio.verdict) ? "success" : "warning";
}

/**
 * The one line that answers "why did I get nothing?".
 *
 * Order matters and is not arbitrary: an upstream error outranks everything
 * because no transcription was attempted; a discarded hallucination outranks a
 * plain empty result because the model DID return text and we threw it away, and
 * a reader who is not told that will reasonably conclude the mic was dead.
 */
export function explain(utterance: Utterance): string | null {
  if (utterance.error) return utterance.error;
  if (utterance.discarded_hallucination) {
    return `Discarded "${utterance.discarded_hallucination}" — invented from ${utterance.audio.verdict.toLowerCase().replace("_", " ")} audio.`;
  }
  if (!utterance.text) return utterance.audio.detail;
  return null;
}

/** RMS as a 0..1 meter fill, matching the server's own 25% full-scale ceiling. */
export const levelFraction = (rmsPct: number) => Math.min(rmsPct / 25, 1);
