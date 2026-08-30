import { apiFetch } from "./client";

/**
 * Push-to-talk transcription.
 *
 * NOTE the deliberate absence of a `content-type` header, for the same reason
 * `uploadDocument` omits one: the browser has to set `multipart/form-data`
 * itself so it can append the boundary. `client.ts` only ever adds
 * `authorization`, so FormData passes straight through.
 *
 * That `authorization` header is the whole reason this works. On every other
 * route it is a Neon Auth JWT; on THIS one it is also where Mantella puts its
 * Whisper credential. The backend tells them apart by shape, so the console's
 * ordinary bearer token authenticates here without a second convention -- and
 * being a known user is what selects your vault key over the server's and keeps
 * your transcripts out of the shared anonymous bucket.
 *
 * `model` is left to the server's default on purpose. It remaps per provider
 * (`upstream_model`), because Groq 400s on `whisper-1` and OpenAI 400s on the
 * large-v3 names; naming one here would break whichever provider is not that one.
 */
export const transcribe = (audio: Blob) => {
  const body = new FormData();
  body.append("file", audio, "mic.wav");
  return apiFetch<{ text: string }>("/v1/audio/transcriptions", { method: "POST", body });
};
