import type { ChatMessage } from "@/types/threads";
import { CopyButton } from "@/components/ui/CopyButton";

/**
 * The transcript, plus the provisional bubble for a turn the server has not
 * written down yet.
 *
 * It is still set as a SCRIPT rather than as a two-sided messaging thread, and
 * that is a decision about the product. In a chat app both sides are weighted
 * equally because two people are talking. Here one side is a person testing and
 * the other is the thing being sold, the NPC's voice, so the reply carries the
 * type and the prompt stays subordinate.
 *
 * What changed: the prompt used to be a bare muted paragraph, which made a long
 * transcript one undifferentiated column with no scannable turn boundaries. It
 * now sits behind a left rule. That marks where a turn starts without promoting
 * the prompt to equal weight, which a filled bubble would.
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

  /*
   * An empty transcript is a REAL state, not a loading one: the project home
   * mounts with no thread at all, and that is where a new user lands after
   * creating their first project. It rendered as nothing above a composer --
   * a blank page with a text box, which says neither what this box does nor
   * that the answer will be grounded in the lore they may not have uploaded yet.
   */
  if (messages.length === 0 && !showDraft) {
    return (
      <div className="flex min-h-[40vh] flex-col justify-center py-10">
        <p className="font-mono mb-2 text-[11px] tracking-[0.14em] text-muted-foreground uppercase">
          No conversation yet
        </p>
        <p className="max-w-prose text-[15px] leading-relaxed text-muted-foreground">
          Say something below and{" "}
          <span className="text-foreground">{speaker ? npc : "an NPC from this world"}</span>{" "}
          answers in this project&rsquo;s voice, citing only this project&rsquo;s lore. What you
          send here goes through the same grounding path the game does, so it is a real test of what
          an NPC will say — not a preview of it.
        </p>
      </div>
    );
  }

  return (
    // aria-live announces the reply a screen reader would otherwise never hear:
    // the transcript grows without a navigation. aria-busy is what keeps that
    // bearable -- it holds the announcement until the stream ends, so the reader
    // gets the finished message once instead of one utterance per token.
    <ol className="space-y-7" aria-live="polite" aria-busy={isStreaming}>
      {messages.map((message) =>
        message.role === "user" ? (
          <li key={message.id} className="border-l-2 border-border pl-4">
            <Speaker name="You" />
            <p className="text-[15px] whitespace-pre-wrap text-muted-foreground">
              {message.content}
            </p>
          </li>
        ) : (
          // `group` so the copy control is revealed by hovering the reply rather
          // than sitting permanently in the margin of every line.
          <li key={message.id} className="group">
            <Speaker name={npc} />
            <p className="text-[15px] leading-[1.7] whitespace-pre-wrap text-foreground">
              {message.content}
            </p>
            <div className="mt-2 flex items-center gap-3">
              {/*
                Only when it is non-null. The four usage columns are nullable BY
                DESIGN (H4) -- a user message has none and some providers report
                none -- so a 0 here would be a fabricated measurement in every
                sum built on it.
              */}
              {message.total_tokens !== null && (
                <p className="font-mono text-[11px] text-muted-foreground">
                  {message.model} · {message.total_tokens} tokens
                </p>
              )}
              {/*
                focus-within, not hover alone: revealed on hover only, the button
                would be reachable by Tab while invisible.
              */}
              <span className="opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100">
                <CopyButton value={message.content} label="Copy" />
              </span>
            </div>
          </li>
        ),
      )}

      {showDraft && (
        <li>
          <Speaker name={npc} />
          <p className="text-[15px] leading-[1.7] whitespace-pre-wrap text-foreground">
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
