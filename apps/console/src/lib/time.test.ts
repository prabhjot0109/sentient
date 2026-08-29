import { describe, expect, it } from "vitest";

import { absoluteTime, parseTimestamp, relativeTime } from "./time";

const NOW = Date.parse("2026-08-29T12:00:00Z");

describe("parseTimestamp", () => {
  it("reads Postgres's zoned ISO string", () => {
    expect(parseTimestamp("2026-08-29T11:00:00+00:00")?.toISOString()).toBe(
      "2026-08-29T11:00:00.000Z",
    );
  });

  it("reads SQLite's zoneless form as UTC rather than as local time", () => {
    // The bug this pins: "2026-08-29 11:00:00" parsed as local time is wrong by
    // the viewer's UTC offset, which on this machine is 5.5 hours.
    expect(parseTimestamp("2026-08-29 11:00:00")?.toISOString()).toBe("2026-08-29T11:00:00.000Z");
  });

  it("returns null for null, empty and unparseable input", () => {
    expect(parseTimestamp(null)).toBeNull();
    expect(parseTimestamp("")).toBeNull();
    expect(parseTimestamp("not a date")).toBeNull();
  });
});

describe("relativeTime", () => {
  it("names the bands", () => {
    expect(relativeTime("2026-08-29T11:59:30Z", NOW)).toBe("just now");
    expect(relativeTime("2026-08-29T11:45:00Z", NOW)).toBe("15m ago");
    expect(relativeTime("2026-08-29T09:00:00Z", NOW)).toBe("3h ago");
    expect(relativeTime("2026-08-27T12:00:00Z", NOW)).toBe("2d ago");
  });

  it("falls back to a date past a week", () => {
    expect(relativeTime("2026-07-04T12:00:00Z", NOW)).toMatch(/Jul/);
  });

  it("never renders the future, so a server clock running ahead reads as 'just now'", () => {
    expect(relativeTime("2026-08-29T12:00:30Z", NOW)).toBe("just now");
  });

  it("renders nothing rather than 'Invalid Date' when there is no timestamp", () => {
    expect(relativeTime(null, NOW)).toBe("");
    expect(relativeTime(undefined, NOW)).toBe("");
  });
});

describe("absoluteTime", () => {
  it("is undefined for a missing value, so it can go straight into a title attribute", () => {
    expect(absoluteTime(null)).toBeUndefined();
  });
});
