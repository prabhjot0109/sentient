import { useCallback, useState } from "react";

/**
 * Read a stored boolean, or `fallback` when there is nothing usable there.
 *
 * Exported, and separate from the hook, so the guard below can be tested at all.
 * The hook itself needs a DOM and this file's suite deliberately runs in `node`
 * (see vite.config.ts) -- the risky part is the try/catch, not the useState
 * around it, so the risky part is what became a function.
 *
 * Every access is wrapped, because `localStorage` is not merely empty in a
 * private window or with site data blocked -- reading it THROWS there, and an
 * unguarded read in a hook initialiser takes the whole app down at mount rather
 * than losing one preference.
 */
export function readPersistedBoolean(key: string, fallback: boolean): boolean {
  try {
    const stored = window.localStorage.getItem(key);
    return stored === null ? fallback : stored === "true";
  } catch {
    return fallback;
  }
}

/**
 * Store a boolean, or drop it silently when storage is unavailable.
 *
 * Dropping it is the correct outcome rather than a swallowed bug: a layout
 * preference is a convenience, never state the app needs back. The value still
 * holds for the rest of the session, because the caller keeps it in React state.
 */
export function writePersistedBoolean(key: string, value: boolean): void {
  try {
    window.localStorage.setItem(key, String(value));
  } catch {
    // Storage is unavailable. See above: losing a preference is not an error.
  }
}

/** A boolean that survives a reload. */
export function usePersistedBoolean(key: string, fallback: boolean) {
  const [value, setValue] = useState(() => readPersistedBoolean(key, fallback));

  const set = useCallback(
    (next: boolean | ((current: boolean) => boolean)) => {
      setValue((current) => {
        const resolved = typeof next === "function" ? next(current) : next;
        writePersistedBoolean(key, resolved);
        return resolved;
      });
    },
    [key],
  );

  return [value, set] as const;
}
