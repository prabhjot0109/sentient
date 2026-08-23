import { useState } from "react";

export function Composer({
  onSend,
  disabled,
}: {
  onSend: (message: string) => void;
  disabled: boolean;
}) {
  const [text, setText] = useState("");

  const submit = () => {
    const message = text.trim();
    if (!message || disabled) return;
    setText("");
    onSend(message);
  };

  return (
    <div className="flex gap-2">
      <textarea
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
        placeholder="Say something to an NPC in this world…"
        className="flex-1 resize-none rounded-md border border-border bg-background px-3 py-2 text-sm"
      />
      <button
        type="button"
        onClick={submit}
        disabled={disabled || !text.trim()}
        className="self-end rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50"
      >
        Send
      </button>
    </div>
  );
}
