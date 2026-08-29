import { afterEach, describe, expect, it } from "vitest";

import { readPersistedBoolean, writePersistedBoolean } from "./persisted";

/**
 * The suite runs in `node`, where `window` does not exist at all -- which is
 * itself one of the cases under test, since an absent `window` throws exactly
 * like a blocked `localStorage` does and must be survived the same way.
 */
type Storage = {
  getItem: (key: string) => string | null;
  setItem: (key: string, value: string) => void;
};

function withStorage(storage: Storage | null) {
  if (storage === null) {
    delete (globalThis as { window?: unknown }).window;
    return;
  }
  (globalThis as { window?: unknown }).window = { localStorage: storage };
}

function memoryStorage() {
  const entries = new Map<string, string>();
  return {
    entries,
    getItem: (key: string) => entries.get(key) ?? null,
    setItem: (key: string, value: string) => void entries.set(key, value),
  };
}

/** A private window, or a browser set to block site data: the accessor throws. */
const hostileStorage: Storage = {
  getItem() {
    throw new DOMException("The operation is insecure.", "SecurityError");
  },
  setItem() {
    throw new DOMException("The operation is insecure.", "SecurityError");
  },
};

afterEach(() => withStorage(null));

describe("readPersistedBoolean", () => {
  it("returns the fallback when nothing is stored, rather than false", () => {
    withStorage(memoryStorage());
    expect(readPersistedBoolean("rail", true)).toBe(true);
    expect(readPersistedBoolean("rail", false)).toBe(false);
  });

  it("reads back exactly what writePersistedBoolean wrote", () => {
    const storage = memoryStorage();
    withStorage(storage);
    writePersistedBoolean("rail", true);
    expect(storage.entries.get("rail")).toBe("true");
    expect(readPersistedBoolean("rail", false)).toBe(true);

    writePersistedBoolean("rail", false);
    expect(readPersistedBoolean("rail", true)).toBe(false);
  });

  it("treats any other stored string as false rather than truthy", () => {
    const storage = memoryStorage();
    storage.entries.set("rail", "yes");
    withStorage(storage);
    expect(readPersistedBoolean("rail", true)).toBe(false);
  });

  it("falls back instead of throwing when the accessor itself throws", () => {
    withStorage(hostileStorage);
    expect(readPersistedBoolean("rail", true)).toBe(true);
  });

  it("falls back instead of throwing when there is no window at all", () => {
    withStorage(null);
    expect(readPersistedBoolean("rail", true)).toBe(true);
  });
});

describe("writePersistedBoolean", () => {
  it("drops the write rather than throwing when storage is unavailable", () => {
    withStorage(hostileStorage);
    expect(() => writePersistedBoolean("rail", true)).not.toThrow();

    withStorage(null);
    expect(() => writePersistedBoolean("rail", true)).not.toThrow();
  });
});
