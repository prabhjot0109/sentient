/**
 * PCM WAV encoding for captured microphone audio.
 *
 * The browser's own `MediaRecorder` would be less code, but it emits webm/opus
 * and the backend's diagnostics read WAV with Python's stdlib `wave` module
 * only. A webm upload still transcribes -- and silently loses everything that
 * makes this endpoint worth proxying. `analyse_wav` degrades to verdict
 * `UNREADABLE`, `UNREADABLE` counts as speech-plausible, and that switches OFF
 * `carries_no_speech`, the filter that discards text Whisper invented from
 * silence. Losing it would let an NPC answer a line nobody spoke, in the console
 * only, while the game path kept the protection.
 *
 * So: 16 kHz mono 16-bit PCM, which is also exactly what Mantella records, so
 * both surfaces land on thresholds fitted to the same kind of capture.
 */

/** Matches Mantella's own capture, and the rate the diagnostics were tuned on. */
export const SAMPLE_RATE = 16000;

const BYTES_PER_SAMPLE = 2;
const HEADER_BYTES = 44;

function writeAscii(view: DataView, offset: number, text: string): void {
  for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i));
}

/**
 * Float samples in [-1, 1] to a RIFF/WAVE blob.
 *
 * Clamped before scaling: Web Audio can hand back values slightly outside the
 * nominal range, and letting those wrap through `setInt16` turns a loud peak
 * into a full-scale sample of the OPPOSITE sign. That reads as an impulse, which
 * is exactly what the clipping detector is looking for -- so unclamped input
 * would manufacture the very warning the diagnostics exist to report.
 */
export function encodeWav(samples: Float32Array, sampleRate: number = SAMPLE_RATE): Blob {
  const dataBytes = samples.length * BYTES_PER_SAMPLE;
  const view = new DataView(new ArrayBuffer(HEADER_BYTES + dataBytes));

  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + dataBytes, true);
  writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true); // fmt chunk length
  view.setUint16(20, 1, true); // 1 = uncompressed PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * BYTES_PER_SAMPLE, true); // byte rate
  view.setUint16(32, BYTES_PER_SAMPLE, true); // block align
  view.setUint16(34, 8 * BYTES_PER_SAMPLE, true); // bits per sample
  writeAscii(view, 36, "data");
  view.setUint32(40, dataBytes, true);

  for (let i = 0; i < samples.length; i += 1) {
    const clamped = Math.max(-1, Math.min(1, samples[i]));
    // Asymmetric on purpose: two's complement int16 reaches -32768 but only
    // +32767, and scaling both directions by 32768 would wrap a full-scale
    // positive peak to the negative rail.
    view.setInt16(44 + i * BYTES_PER_SAMPLE, clamped * (clamped < 0 ? 0x8000 : 0x7fff), true);
  }

  return new Blob([view.buffer], { type: "audio/wav" });
}
