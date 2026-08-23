import { describe, expect, it } from "vitest";

import { formatBytes, statusLabel } from "./format";

describe("formatBytes", () => {
  it("renders an em dash when the store has no size", () => {
    expect(formatBytes(null)).toBe("—");
  });

  it("renders small files in bytes", () => {
    expect(formatBytes(177)).toBe("177 B");
  });

  it("renders KB to one decimal", () => {
    expect(formatBytes(2048)).toBe("2.0 KB");
  });

  it("renders MB to one decimal", () => {
    expect(formatBytes(26_214_400)).toBe("25.0 MB");
  });

  it("treats zero as a real size, not a missing one", () => {
    expect(formatBytes(0)).toBe("0 B");
  });
});

describe("statusLabel", () => {
  it("names each of the four backend statuses in the user's terms", () => {
    expect(statusLabel("processing")).toBe("Indexing…");
    expect(statusLabel("ready")).toBe("Ready");
    expect(statusLabel("failed")).toBe("Failed");
    expect(statusLabel("reindexing")).toBe("Re-embedding…");
  });
});
