import { Loader2, Mic } from "lucide-react";
import { useRef, useState } from "react";

import { describe } from "@/lib/api/messages";

import { useTranscribe } from "../hooks";
import { MIN_HOLD_MS, startCapture, tooShort, type Capture } from "../recorder";

type Phase = "idle" | "recording" | "sending";

/**
 * Push to talk.
 *
 * Hold, speak, release. Deliberately not hands-free: voice activity detection
 * needs silence thresholds and echo suppression tuned against real captures,
 * and its failure mode -- sending a half-heard sentence to an NPC nobody meant
 * to address -- is worse than the failure mode of a button.
 *
 * The transcript fills the composer rather than sending itself. Whisper mishears
 * proper nouns, and a fantasy world is almost entirely proper nouns, so the last
 * word belongs to the person who spoke.
 */
export function MicButton({
  onTranscript,
  onNotice,
  disabled,
}: {
  onTranscript: (text: string) => void;
  onNotice: (text: string | null) => void;
  disabled: boolean;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const capture = useRef<Capture | null>(null);
  const startedAt = useRef(0);
  const transcribe = useTranscribe();

  const begin = async (event: { currentTarget: HTMLElement; pointerId?: number }) => {
    if (phase !== "idle" || disabled) return;
    // Capture the pointer so releasing OFF the button still ends the recording.
    // Without this, dragging away mid-sentence leaves the microphone open and
    // the browser's recording indicator lit.
    if (event.pointerId !== undefined) {
      event.currentTarget.setPointerCapture?.(event.pointerId);
    }
    onNotice(null);
    setPhase("recording");
    startedAt.current = Date.now();
    try {
      capture.current = await startCapture();
    } catch {
      setPhase("idle");
      // The overwhelmingly common cause is a denied permission, and the fix is
      // in browser chrome this app cannot reach -- so say where to go, rather
      // than reporting the DOMException, which names no action.
      onNotice("Microphone unavailable. Allow access from the icon in your address bar.");
    }
  };

  const end = async () => {
    if (phase !== "recording") return;
    const held = Date.now() - startedAt.current;
    const session = capture.current;
    capture.current = null;
    if (!session) {
      setPhase("idle");
      return;
    }

    // Rejected before the upload, not after. A hold this short usually catches a
    // stream that has not finished opening, so the audio is all zeros: the
    // backend would measure it, discard the model's invented text and return
    // nothing, having spent a round trip to say so.
    if (tooShort(held)) {
      session.cancel();
      setPhase("idle");
      onNotice(`Hold the button for at least ${(MIN_HOLD_MS / 1000).toFixed(1)}s while speaking.`);
      return;
    }

    setPhase("sending");
    try {
      const { text } = await transcribe.mutateAsync(await session.stop());
      // An empty string is a real answer here, not a failure. The backend
      // returns one when the waveform held no speech, or when it discarded text
      // Whisper invented from silence -- and the reason is in the server log
      // beside the measured levels.
      if (text.trim()) {
        onTranscript(text.trim());
      } else {
        onNotice("Nothing was heard. Check the input device and try again.");
      }
    } catch (error) {
      onNotice(describe(error).body);
    } finally {
      setPhase("idle");
    }
  };

  const busy = phase === "sending";
  const recording = phase === "recording";

  return (
    <button
      type="button"
      disabled={disabled || busy}
      aria-label={recording ? "Recording — release to transcribe" : "Hold to speak"}
      aria-pressed={recording}
      onPointerDown={begin}
      onPointerUp={end}
      onPointerCancel={end}
      // Space and Enter are the keyboard equivalents of a press. `repeat` is
      // checked because holding a key fires keydown continuously, which would
      // otherwise restart the capture every few milliseconds.
      onKeyDown={(e) => {
        if ((e.key === " " || e.key === "Enter") && !e.repeat) {
          e.preventDefault();
          void begin(e);
        }
      }}
      onKeyUp={(e) => {
        if (e.key === " " || e.key === "Enter") {
          e.preventDefault();
          void end();
        }
      }}
      className={`inline-flex size-8 shrink-0 items-center justify-center rounded-full transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:opacity-30 ${
        recording
          ? "bg-destructive text-destructive-foreground"
          : "bg-muted text-muted-foreground hover:text-foreground"
      }`}
    >
      {busy ? <Loader2 className="size-4 animate-spin" /> : <Mic className="size-4" />}
    </button>
  );
}
