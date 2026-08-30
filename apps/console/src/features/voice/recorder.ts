import { encodeWav, SAMPLE_RATE } from "./wav";

/**
 * The shortest hold worth uploading, in milliseconds.
 *
 * Lifted from `adapters/stt/diagnostics.py::PTT_RACE_DURATION_S = 0.7`, whose
 * comment records what it is for: push-to-talk holds shorter than this
 * frequently capture a stream that has not finished opening, which is what
 * produces the all-zero WAV files. That threshold was fitted to real captures,
 * so a tap is rejected here rather than spent on an upload and a provider call
 * that can only come back empty.
 */
export const MIN_HOLD_MS = 700;

/** Whether a hold was too short to have plausibly captured anything. */
export const tooShort = (heldMs: number): boolean => heldMs < MIN_HOLD_MS;

export type Capture = {
  /** Tears down the graph and returns the captured audio as a WAV blob. */
  stop: () => Promise<Blob>;
  /** Tears down the graph and discards the audio. */
  cancel: () => void;
};

/**
 * Open the microphone and start accumulating PCM.
 *
 * `ScriptProcessorNode` is deprecated in favour of `AudioWorklet`, and is still
 * the right tool here: a worklet has to live in its own module fetched by URL,
 * which buys nothing for a capture that lasts a couple of seconds and exists
 * only to fill an array. It remains supported everywhere the console runs.
 */
export async function startCapture(): Promise<Capture> {
  const stream = await navigator.mediaDevices.getUserMedia({
    // Mono at the source. Asking for one channel here means no downmix later,
    // and echo cancellation matters even for push-to-talk once anything else on
    // the page can make noise.
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });

  const context = new AudioContext({ sampleRate: SAMPLE_RATE });
  const source = context.createMediaStreamSource(stream);
  const processor = context.createScriptProcessor(4096, 1, 1);
  const chunks: Float32Array[] = [];

  processor.onaudioprocess = (event) => {
    // Copied, not referenced: the event's buffer is reused by the audio thread
    // for the next block, so keeping the view would leave every chunk pointing
    // at the same (last) few milliseconds of sound.
    chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
  };

  // A ScriptProcessor only runs while it is connected to the destination, but
  // connecting the microphone to the speakers is how you get a feedback howl.
  // A gain of zero satisfies the graph without making a sound.
  const silence = context.createGain();
  silence.gain.value = 0;
  source.connect(processor);
  processor.connect(silence);
  silence.connect(context.destination);

  const teardown = async () => {
    processor.onaudioprocess = null;
    processor.disconnect();
    silence.disconnect();
    source.disconnect();
    // Releasing the tracks is what turns off the browser's recording indicator.
    // Leaving them live reads to the user as "this page is still listening".
    stream.getTracks().forEach((track) => track.stop());
    await context.close();
  };

  return {
    async stop() {
      // The context's ACTUAL rate, not the requested one: the constructor's
      // sampleRate is a request, and a device that cannot honour it leaves the
      // context at its own rate. Writing 16000 into the header of 48 kHz audio
      // would not fail -- it would transcribe speech played at a third speed.
      const rate = context.sampleRate;
      await teardown();

      const total = chunks.reduce((count, chunk) => count + chunk.length, 0);
      const merged = new Float32Array(total);
      let offset = 0;
      for (const chunk of chunks) {
        merged.set(chunk, offset);
        offset += chunk.length;
      }
      return encodeWav(merged, rate);
    },
    cancel() {
      void teardown();
    },
  };
}
