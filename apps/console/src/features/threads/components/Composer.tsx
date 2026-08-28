import { ArrowUp } from "lucide-react";
import { useState } from "react";

/**
 * One panel, not a textarea beside a button.
 *
 * The border and the focus ring sit on the panel and the textarea inside it is
 * transparent and borderless, so the whole composer reads as one control -- and
 * a keyboard user sees the ring around the thing they are typing into rather
 * than around an input that happens to be part of it.
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
  const ready = text.trim().length > 0 && !disabled;

  const submit = () => {
    if (!ready) return;
    setText("");
    onSend(text.trim());
  };

  return (
    <div className="rounded-xl border border-border bg-card p-2 transition-colors focus-within:border-ring">
      <textarea
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
        rows={2}
        placeholder={placeholder}
        className="block w-full resize-none bg-transparent px-2 pt-1.5 text-[15px] placeholder:text-muted-foreground focus:outline-none"
      />
      <div className="flex items-center justify-between gap-3 px-2 pb-0.5">
        <p className="text-xs text-muted-foreground">
          {disabled ? "Answering…" : "Enter to send · Shift+Enter for a new line"}
        </p>
        <button
          type="button"
          onClick={submit}
          disabled={!ready}
          aria-label="Send message"
          className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-opacity hover:opacity-90 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:opacity-30"
        >
          <ArrowUp className="size-4" />
        </button>
      </div>
    </div>
  );
}
