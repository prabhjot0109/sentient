import { describe, expect, it } from "vitest";

import { parseSseFrames } from "./sse";

/** Feeds exactly the byte chunks given, so a test can put a boundary anywhere. */
const streamOf = (chunks: string[]): ReadableStream<Uint8Array> => {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
};

const collect = async (chunks: string[]) => {
  const out: string[] = [];
  for await (const frame of parseSseFrames(streamOf(chunks))) out.push(frame);
  return out;
};

describe("parseSseFrames", () => {
  it("yields each frame's data payload", async () => {
    expect(await collect(['data: {"a":1}\n\n', 'data: {"b":2}\n\n'])).toEqual([
      '{"a":1}',
      '{"b":2}',
    ]);
  });

  it("reassembles a frame split across byte chunks", async () => {
    // The case a naive split() loses. A reader hands you arbitrary chunk
    // boundaries and this one lands mid-payload.
    expect(await collect(['data: {"a"', ":1}\n\n"])).toEqual(['{"a":1}']);
  });

  it("reassembles a frame whose terminator is split", async () => {
    expect(await collect(['data: {"a":1}\n', '\ndata: {"b":2}\n\n'])).toEqual([
      '{"a":1}',
      '{"b":2}',
    ]);
  });

  it("yields several frames arriving in one chunk", async () => {
    expect(await collect(['data: {"a":1}\n\ndata: {"b":2}\n\n'])).toEqual(['{"a":1}', '{"b":2}']);
  });

  it("passes [DONE] through as a payload", async () => {
    expect(await collect(["data: [DONE]\n\n"])).toEqual(["[DONE]"]);
  });

  it("ignores keep-alive comments and blank frames", async () => {
    expect(await collect([": keep-alive\n\n", 'data: {"a":1}\n\n'])).toEqual(['{"a":1}']);
  });

  it("yields a trailing frame with no terminator", async () => {
    // A stream that ends without a final \n\n still carried a real frame.
    expect(await collect(['data: {"a":1}'])).toEqual(['{"a":1}']);
  });

  it("reassembles a multi-byte character split across chunks", async () => {
    // The reason decode() is called with { stream: true }. Decoding each chunk
    // independently turns the halves into two replacement characters, and the
    // NPC's dialogue quietly fills with U+FFFD.
    const bytes = new TextEncoder().encode('data: {"c":"é"}\n\n');
    const split = [bytes.slice(0, 12), bytes.slice(12)];
    const out: string[] = [];
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const part of split) controller.enqueue(part);
        controller.close();
      },
    });
    for await (const frame of parseSseFrames(stream)) out.push(frame);
    expect(out).toEqual(['{"c":"é"}']);
  });

  it("parses the bytes the server actually sends", async () => {
    // Copied from a live stream on 2026-08-23, groq / openai/gpt-oss-20b. The
    // server's json.dumps puts a space after every colon; a fixture written by
    // hand would not have one, and would not have exercised it.
    const meta =
      'data: {"object": "sentient.chat.meta", "thread_id": "3b4b4efd-d86a-4537-89a1-6610583502ae", "sources": [], "top_k": 4}\n\n';
    const chunk =
      'data: {"id": "chatcmpl-77ad7b7bf48d4392925779b80adf3940", "object": "chat.completion.chunk", "created": 1787506150, "model": "openai/gpt-oss-20b", "choices": [{"index": 0, "delta": {"content": "I"}, "finish_reason": null}]}\n\n';
    const frames = await collect([meta + chunk, "data: [DONE]\n\n"]);
    expect(frames).toHaveLength(3);
    expect(JSON.parse(frames[0]).object).toBe("sentient.chat.meta");
    expect(JSON.parse(frames[1]).choices[0].delta.content).toBe("I");
    expect(frames[2]).toBe("[DONE]");
  });
});
