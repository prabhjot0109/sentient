/**
 * Turns a byte stream into SSE `data:` payloads.
 *
 * The buffer is the entire point. A reader hands you arbitrary chunk boundaries,
 * so a frame terminator routinely lands mid-chunk; the obvious
 * `decode(value).split("\n\n")` drops whatever straddles it, which presents as
 * tokens occasionally going missing under load and is close to undebuggable from
 * the UI.
 *
 * `stream: true` on `decode` matters for the same reason one level down: a
 * multi-byte UTF-8 character can be split across chunks, and decoding each chunk
 * independently turns it into a replacement character.
 */
export async function* parseSseFrames(stream: ReadableStream<Uint8Array>): AsyncGenerator<string> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const framesIn = (text: string): string[] => {
    const parts = text.split("\n\n");
    // The tail is whatever has not been terminated yet. It becomes the head of
    // the next read rather than being yielded half-formed.
    buffer = parts.pop() ?? "";
    return parts;
  };

  const payloadOf = (frame: string): string | null => {
    const line = frame.split("\n").find((l) => l.startsWith("data:"));
    return line ? line.slice("data:".length).trim() : null;
  };

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      for (const frame of framesIn(buffer)) {
        const payload = payloadOf(frame);
        if (payload) yield payload;
      }
    }
    // A stream that ends without a final terminator still carried a real frame.
    const payload = payloadOf(buffer);
    if (payload) yield payload;
  } finally {
    reader.releaseLock();
  }
}
