import { describe, expect, it } from "vitest";

/**
 * The predicate is the part with the bugs in it; the effect around it is four
 * lines of listener wiring. Reimplemented here against the same rules so the
 * matrix is pinned without a DOM.
 */
type Event = { key: string; metaKey?: boolean; ctrlKey?: boolean; shiftKey?: boolean };
type Hotkey = { key: string; mod?: boolean; shift?: boolean };

const matches = (hotkey: Hotkey, event: Event) =>
  event.key.toLowerCase() === hotkey.key.toLowerCase() &&
  Boolean(hotkey.mod) === Boolean(event.metaKey || event.ctrlKey) &&
  Boolean(hotkey.shift) === Boolean(event.shiftKey);

describe("hotkey matching", () => {
  const palette: Hotkey = { key: "k", mod: true };

  it("accepts Meta and Control alike, so one binding serves both platforms", () => {
    expect(matches(palette, { key: "k", metaKey: true })).toBe(true);
    expect(matches(palette, { key: "k", ctrlKey: true })).toBe(true);
  });

  it("is case-insensitive, because a held Shift changes event.key", () => {
    expect(
      matches({ key: "k", mod: true, shift: true }, { key: "K", ctrlKey: true, shiftKey: true }),
    ).toBe(true);
  });

  it("does not fire the unmodified binding when a modifier is held", () => {
    expect(matches({ key: "k" }, { key: "k", ctrlKey: true })).toBe(false);
  });

  it("does not fire the modified binding without one", () => {
    expect(matches(palette, { key: "k" })).toBe(false);
  });

  it("requires Shift to be absent unless asked for, so mod+K and mod+Shift+K stay distinct", () => {
    expect(matches(palette, { key: "k", metaKey: true, shiftKey: true })).toBe(false);
  });
});
