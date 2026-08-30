import { ArrowUp } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";

import { MicButton } from "@/features/voice";

/** Roughly ten lines. Past this the composer scrolls instead of eating the transcript. */
const MAX_HEIGHT = 220;

/**
 * One panel, not a textarea beside a button.
 *
 * The border and the focus ring sit on the panel and the textarea inside it is
 * transparent and borderless, so the whole composer reads as one control -- and
 * a keyboard user sees the ring around the thing they are typing into rather
 * than around an input that happens to be part of it.
 *
 * The box grows with the message. It was `rows={2}`, which is wrong in both
 * directions: it wasted two lines on the common one-line prompt, and it hid the
 * top of a long one behind an inner scrollbar. Height is measured from
 * `scrollHeight` and capped, so a pasted wall of text stops at ten lines rather
 * than pushing the transcript off screen.
 */
export function Composer({
  onSend,
  disabled,
  placeholder = "Say something to an NPC in this world…",
}: {
  onSend: (message: string) => void;
  disabled: boolean;
  placeholder?: string;
}) {
  const [text, setText] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  const ready = text.trim().length > 0 && !disabled;

  /**
   * A transcript is APPENDED, not assigned. Someone who typed half a sentence
   * and then spoke the rest means both halves, and overwriting is the one
   * outcome they cannot undo without retyping.
   */
  const appendTranscript = (transcript: string) => {
    setNotice(null);
    setText((current) => (current.trim() ? `${current.trimEnd()} ${transcript}` : transcript));
    box.current?.focus();
  };

  // Layout effect, not effect: this runs before paint, so growing by a line
  // never shows the user a frame at the old height.
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    // Collapse first. scrollHeight can only report content TALLER than the
    // current height, so without this the box grows and never shrinks back.
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
  }, [text]);

  const submit = () => {
    if (!ready) return;
    setText("");
    onSend(text.trim());
  };

  return (
    <div className="rounded-2xl border border-border bg-card shadow-sm transition-colors focus-within:border-ring">
      <textarea
        ref={box}
        aria-label="Message"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          // Enter sends, Shift+Enter breaks the line. The opposite convention
          // makes a chat box feel broken.
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        rows={1}
        placeholder={placeholder}
        className="block max-h-[220px] w-full resize-none bg-transparent px-4 pt-3.5 text-[15px] leading-relaxed placeholder:text-muted-foreground focus:outline-none"
      />
      <div className="flex items-center justify-between gap-3 px-3 pb-3">
        {/*
          One slot, three messages. A voice notice REPLACES the keyboard hint
          rather than appearing beside it: the hint is ambient and the notice is
          the answer to something the reader just did, so showing both makes the
          one that matters compete with the one that does not.

          aria-live so a screen reader hears "nothing was heard" without having
          to go looking for it -- the whole interaction happens with the button
          held, and focus never moves.
        */}
        <p className="text-xs text-muted-foreground" aria-live="polite">
          {notice ?? (disabled ? "Answering…" : "Hold the mic to speak · Enter to send")}
        </p>
        {/* Grouped, so `justify-between` splits hint-from-controls rather than
            spreading three items evenly and stranding the mic mid-row. */}
        <div className="flex shrink-0 items-center gap-2">
          <MicButton onTranscript={appendTranscript} onNotice={setNotice} disabled={disabled} />
          <button
            type="button"
            onClick={submit}
            disabled={!ready}
            aria-label="Send message"
            className="inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-opacity hover:opacity-90 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:opacity-30"
          >
            <ArrowUp className="size-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
