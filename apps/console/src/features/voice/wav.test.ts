import { describe, expect, it } from "vitest";

import { MIN_HOLD_MS, tooShort } from "./recorder";
import { encodeWav, SAMPLE_RATE } from "./wav";

const ascii = (view: DataView, offset: number, length: number) =>
  Array.from({ length }, (_, i) => String.fromCharCode(view.getUint8(offset + i))).join("");

const parse = async (blob: Blob) => new DataView(await blob.arrayBuffer());

const tone = (samples: number) =>
  Float32Array.from({ length: samples }, (_, i) => Math.sin((i / SAMPLE_RATE) * 2 * Math.PI * 220));

describe("encodeWav", () => {
  it("writes a RIFF/WAVE container Python's wave module can open", async () => {
    const view = await parse(encodeWav(tone(1000)));
    expect(ascii(view, 0, 4)).toBe("RIFF");
    expect(ascii(view, 8, 4)).toBe("WAVE");
    expect(ascii(view, 12, 4)).toBe("fmt ");
    expect(ascii(view, 36, 4)).toBe("data");
  });

  it("declares uncompressed mono 16-bit, which is what analyse_wav reads", async () => {
    const view = await parse(encodeWav(tone(1000)));
    expect(view.getUint16(20, true)).toBe(1); // PCM, not a compressed codec
    expect(view.getUint16(22, true)).toBe(1); // mono
    expect(view.getUint16(34, true)).toBe(16); // bits per sample
  });

  it("writes the ACTUAL capture rate, not the requested one", async () => {
    // A device that cannot honour 16 kHz leaves the context at its own rate.
    // Writing 16000 into the header of 48 kHz audio does not fail -- it
    // transcribes speech played at a third speed.
    const view = await parse(encodeWav(tone(100), 48000));
    expect(view.getUint32(24, true)).toBe(48000);
    expect(view.getUint32(28, true)).toBe(48000 * 2); // byte rate follows it
  });

  it("agrees with itself about how much audio it holds", async () => {
    const view = await parse(encodeWav(tone(1234)));
    expect(view.getUint32(40, true)).toBe(1234 * 2); // data chunk
    expect(view.getUint32(4, true)).toBe(36 + 1234 * 2); // RIFF chunk
    expect(view.byteLength).toBe(44 + 1234 * 2);
  });

  it("clamps instead of wrapping, so a loud peak is not read as clipping", async () => {
    // Web Audio can return values slightly outside [-1, 1]. Unclamped, +1.5
    // wraps through setInt16 to a large NEGATIVE sample -- an impulse, which is
    // exactly the shape the clipping detector reports on.
    const view = await parse(encodeWav(Float32Array.from([1.5, -1.5])));
    expect(view.getInt16(44, true)).toBe(32767);
    expect(view.getInt16(46, true)).toBe(-32768);
  });

  it("survives an empty capture rather than producing a broken header", async () => {
    const view = await parse(encodeWav(new Float32Array(0)));
    expect(view.byteLength).toBe(44);
    expect(view.getUint32(40, true)).toBe(0);
  });
});

describe("tooShort", () => {
  it("matches the backend's measured push-to-talk race window", () => {
    // adapters/stt/diagnostics.py::PTT_RACE_DURATION_S = 0.7. If that moves,
    // this must move with it -- the point is to reject a tap BEFORE spending an
    // upload and a provider call on audio that cannot contain speech.
    expect(MIN_HOLD_MS).toBe(700);
  });

  it("rejects a tap", () => {
    expect(tooShort(0)).toBe(true);
    expect(tooShort(699)).toBe(true);
  });

  it("accepts a real hold", () => {
    expect(tooShort(700)).toBe(false);
    expect(tooShort(2400)).toBe(false);
  });
});
