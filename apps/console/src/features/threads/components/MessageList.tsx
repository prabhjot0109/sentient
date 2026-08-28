import type { ChatMessage } from "@/types/threads";

/**
 * The transcript, plus the provisional bubble for a turn the server has not
 * written down yet.
 *
 * It is set as a SCRIPT, not as a two-sided messaging thread, and that is a
 * decision about the product rather than a style. In a chat app both sides are
 * weighted equally because two people are talking. Here one side is a person
 * testing and the other is the thing being sold -- the NPC's voice -- so the
 * reply carries the type and the prompt gets out of its way.
 *
 * `showDraft` is decided by `transcript.ts` rather than here, because the answer
 * is neither "while streaming" (the reply would blank for the 1.3-1.7s the
 * deferred write takes) nor "whenever there is a draft" (it would render twice
 * once the row lands).
 */
export function MessageList({
  messages,
  draft,
  showDraft,
  isStreaming,
  speaker,
}: {
  messages: ChatMessage[];
  draft: string;
  showDraft: boolean;
  isStreaming: boolean;
  /** The NPC this thread belongs to, when the game path named one. */
  speaker?: string | null;
}) {
  const npc = speaker || "NPC";

  return (
    // aria-live announces the reply a screen reader would otherwise never hear:
    // the transcript grows without a navigation. aria-busy is what keeps that
    // bearable -- it holds the announcement until the stream ends, so the reader
    // gets the finished message once instead of one utterance per token.
    <ol className="space-y-8" aria-live="polite" aria-busy={isStreaming}>
      {messages.map((message) => (
        <li key={message.id}>
          <Speaker name={message.role === "user" ? "You" : npc} />
          {message.role === "user" ? (
            <p className="whitespace-pre-wrap text-[15px] text-muted-foreground">
              {message.content}
            </p>
          ) : (
            <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-foreground">
              {message.content}
            </p>
          )}
          {/*
            Only when it is non-null. The four usage columns are nullable BY
            DESIGN (H4) -- a user message has none and some providers report none
            -- so a 0 here would be a fabricated measurement in every sum built
            on it.
          */}
          {message.total_tokens !== null && (
            <p className="font-mono mt-2 text-[11px] text-muted-foreground">
              {message.model} · {message.total_tokens} tokens
            </p>
          )}
        </li>
      ))}

      {showDraft && (
        <li>
          <Speaker name={npc} />
          <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-foreground">
            {draft}
            {/*
              The one place --brand is spent on this surface. A caret is the
              only thing on the page that is genuinely live, so it is the only
              thing that earns the accent.
            */}
            {isStreaming && (
              <span aria-hidden className="ml-0.5 animate-pulse text-brand">
                ▍
              </span>
            )}
          </p>
        </li>
      )}
    </ol>
  );
}

/**
 * Small caps in the mono face. The speaker is metadata about the line, not part
 * of it, and the width-consistent face is what keeps a column of them looking
 * like a margin rather than like more dialogue.
 */
function Speaker({ name }: { name: string }) {
  return (
    <p className="font-mono mb-1.5 text-[11px] tracking-[0.14em] text-muted-foreground uppercase">
      {name}
    </p>
  );
}
