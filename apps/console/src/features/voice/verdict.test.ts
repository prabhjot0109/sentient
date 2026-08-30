import { describe as group, expect, it } from "vitest";

import type { Utterance } from "@/types/voice";

import { explain, levelFraction, toneOf } from "./verdict";

const utterance = (over: Partial<Utterance> = {}): Utterance => ({
  time: "17:28:28",
  text: "I am a humble Nord.",
  provider: "groq",
  model: "whisper-large-v3-turbo",
  error: null,
  elapsed_s: 0.31,
  audio: {
    verdict: "OK",
    detail: "speech-level audio",
    byte_size: 48044,
    duration_s: 1.5,
    sample_rate: 16000,
    channels: 1,
    rms_pct: 14.8,
    peak_pct: 62,
    clipped_pct: 0,
    warnings: [],
  },
  ...over,
});

const withAudio = (over: Partial<Utterance["audio"]>, rest: Partial<Utterance> = {}) =>
  utterance({ ...rest, audio: { ...utterance().audio, ...over } });

group("toneOf", () => {
  it("reads healthy audio as success", () => {
    expect(toneOf(utterance())).toBe("success");
    expect(toneOf(withAudio({ verdict: "HOT" }))).toBe("success");
  });

  it("reads every audio problem as warning, not danger", () => {
    // Deliberate: `bg-destructive/10 text-destructive` is the combination
    // tokens.css records as a KNOWN GAP at 3.64:1 in dark mode. The common case
    // must be the accessible one.
    for (const verdict of ["SILENT", "VERY_QUIET", "TOO_SHORT", "UNREADABLE"]) {
      expect(toneOf(withAudio({ verdict }))).toBe("warning");
    }
  });

  it("reserves danger for an upstream failure", () => {
    expect(toneOf(utterance({ error: "groq STT failed: 401" }))).toBe("danger");
  });

  it("lets an upstream failure outrank a healthy waveform", () => {
    expect(toneOf(utterance({ error: "boom", audio: utterance().audio }))).toBe("danger");
  });
});

group("explain", () => {
  it("says nothing when there is a transcript and no incident", () => {
    expect(explain(utterance())).toBeNull();
  });

  it("surfaces an upstream error above everything else", () => {
    const failed = utterance({ error: "groq STT failed: 401", text: "" });
    expect(explain(failed)).toBe("groq STT failed: 401");
  });

  it("says text was DISCARDED rather than letting it read as a dead mic", () => {
    // The model returned words and we threw them away. A reader not told that
    // will reasonably conclude the microphone failed, and go fix the wrong thing.
    const hallucinated = withAudio(
      { verdict: "SILENT" },
      { text: "", discarded_hallucination: "Thank you." },
    );
    const note = explain(hallucinated);
    expect(note).toContain("Discarded");
    expect(note).toContain("Thank you.");
    expect(note).toContain("silent");
  });

  it("falls back to the measured detail for a plain empty result", () => {
    const quiet = withAudio({ verdict: "VERY_QUIET", detail: "mic barely open" }, { text: "" });
    expect(explain(quiet)).toBe("mic barely open");
  });
});

group("levelFraction", () => {
  it("treats 25% RMS as a full meter, matching the server's own ceiling", () => {
    expect(levelFraction(25)).toBe(1);
    expect(levelFraction(12.5)).toBe(0.5);
  });

  it("clamps a hot capture instead of overflowing the bar", () => {
    expect(levelFraction(80)).toBe(1);
  });

  it("reports silence as empty", () => {
    expect(levelFraction(0)).toBe(0);
  });
});
