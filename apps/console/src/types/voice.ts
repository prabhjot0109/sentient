/**
 * Mirrors `services/transcription.recent_history` and
 * `adapters/stt/diagnostics.AudioReport.as_dict`.
 *
 * This buffer is IN-MEMORY on the server: a per-user list capped at 50 entries
 * that does not survive a restart and is never written to the database. That is
 * deliberate -- it holds raw transcribed speech, and the measurements exist to
 * answer "why did my microphone produce nothing?", not to be a record of the
 * conversation. The conversation itself lives in `chat_messages`.
 */

/** The waveform measurements, from the stdlib `wave` reader plus numpy. */
export type AudioReport = {
  /** SILENT | VERY_QUIET | OK | HOT | TOO_SHORT | UNREADABLE. */
  verdict: string;
  detail: string;
  byte_size: number;
  duration_s: number;
  sample_rate: number;
  channels: number;
  rms_pct: number;
  peak_pct: number;
  clipped_pct: number;
  warnings: string[];
};

/**
 * One utterance.
 *
 * `elapsed_s` is absent on the error path, which records a different set of
 * fields -- hence the optionals rather than nullables. `discarded_hallucination`
 * is the text the model invented from audio that held no speech, kept so the
 * reason for an empty result is visible rather than merely asserted.
 */
export type Utterance = {
  time: string;
  text: string;
  provider: string;
  model: string;
  error: string | null;
  audio: AudioReport;
  elapsed_s?: number;
  discarded_hallucination?: string;
};

export type RecentTranscriptions = {
  count: number;
  empty_transcriptions: number;
  transcriptions: Utterance[];
};
