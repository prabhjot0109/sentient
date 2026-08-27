import type { ChatMessage } from "@/types/threads";

/**
 * The transcript, plus the provisional bubble for a turn the server has not
 * written down yet.
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
}: {
  messages: ChatMessage[];
  draft: string;
  showDraft: boolean;
  isStreaming: boolean;
}) {
  return (
    // aria-live announces the reply a screen reader would otherwise never hear:
    // the transcript grows without a navigation. aria-busy is what keeps that
    // bearable -- it holds the announcement until the stream ends, so the reader
    // gets the finished message once instead of one utterance per token.
    <ol className="space-y-3" aria-live="polite" aria-busy={isStreaming}>
      {messages.map((message) => (
        <li key={message.id} className="space-y-1">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">{message.role}</p>
          <p className="whitespace-pre-wrap text-sm">{message.content}</p>
          {/*
            Only when it is non-null. The four usage columns are nullable BY
            DESIGN (H4) -- a user message has none and some providers report none
            -- so a 0 here would be a fabricated measurement in every sum built
            on it.
          */}
          {message.total_tokens !== null && (
            <p className="text-xs text-muted-foreground">
              {message.model} · {message.total_tokens} tokens
            </p>
          )}
        </li>
      ))}
      {showDraft && (
        <li className="space-y-1">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">assistant</p>
          <p className="whitespace-pre-wrap text-sm">
            {draft}
            {isStreaming && <span className="animate-pulse">▍</span>}
          </p>
        </li>
      )}
    </ol>
  );
}
