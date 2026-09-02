import { describe, expect, it } from "vitest";

import { describeBatch, uploadAll } from "./batch";

const file = (name: string) => new File(["lore"], name, { type: "application/pdf" });

describe("uploadAll", () => {
  it("uploads every file and returns the server's sanitised names", async () => {
    const seen: string[] = [];
    const result = await uploadAll([file("a.pdf"), file("b.pdf")], async (f) => {
      seen.push(f.name);
      return { filename: f.name.replace(".pdf", "_clean.pdf") };
    });

    expect(seen).toEqual(["a.pdf", "b.pdf"]);
    expect(result.uploaded).toEqual(["a_clean.pdf", "b_clean.pdf"]);
    expect(result.failed).toEqual([]);
  });

  it("uploads one at a time, in the order the user picked", async () => {
    // Parallel would trip RATE_LIMIT_UPLOADS_PER_HOUR on a burst and would let
    // the rows arrive in an order that does not match the list the user saw.
    const inFlight: string[] = [];
    let maxConcurrent = 0;

    await uploadAll([file("a.pdf"), file("b.pdf"), file("c.pdf")], async (f) => {
      inFlight.push(f.name);
      maxConcurrent = Math.max(maxConcurrent, inFlight.length);
      await Promise.resolve();
      inFlight.pop();
      return { filename: f.name };
    });

    expect(maxConcurrent).toBe(1);
  });

  it("keeps going after one file fails", async () => {
    const result = await uploadAll(
      [file("ok.pdf"), file("bad.exe"), file("also-ok.pdf")],
      async (f) => {
        if (f.name === "bad.exe") throw new Error("Only PDF and TXT files are supported");
        return { filename: f.name };
      },
    );

    expect(result.uploaded).toEqual(["ok.pdf", "also-ok.pdf"]);
    expect(result.failed.map((f) => f.name)).toEqual(["bad.exe"]);
  });

  it("throws the original error when nothing succeeded", async () => {
    // The single-file path must behave exactly as it did before batching: the
    // backend's own sentence reaches ErrorState, not a summary wrapping it.
    const backendError = new Error("Only PDF and TXT files are supported");

    await expect(
      uploadAll([file("bad.exe")], async () => {
        throw backendError;
      }),
    ).rejects.toBe(backendError);
  });

  it("does not throw when some files succeeded", async () => {
    // The successes are real and already indexing. Raising would tell the user to
    // retry files that are on the server.
    const result = await uploadAll([file("ok.pdf"), file("bad.exe")], async (f) => {
      if (f.name === "bad.exe") throw new Error("rejected");
      return { filename: f.name };
    });

    expect(result.uploaded).toEqual(["ok.pdf"]);
    expect(result.failed).toHaveLength(1);
  });

  it("handles an empty selection without calling the server", async () => {
    let calls = 0;
    const result = await uploadAll([], async () => {
      calls += 1;
      return { filename: "never" };
    });

    expect(calls).toBe(0);
    expect(result).toEqual({ uploaded: [], failed: [] });
  });
});

describe("describeBatch", () => {
  it("names the file when there is exactly one", () => {
    expect(describeBatch({ uploaded: ["lore.pdf"], failed: [] }).title).toBe("Uploading lore.pdf");
  });

  it("counts them when there are several", () => {
    expect(describeBatch({ uploaded: ["a.pdf", "b.pdf"], failed: [] }).title).toBe(
      "Uploading 2 files",
    );
  });

  it("names the failures rather than counting them", () => {
    // "2 files failed" sends the user back to the picker to work out which two.
    const copy = describeBatch({
      uploaded: ["a.pdf"],
      failed: [
        { name: "big.pdf", error: new Error("too large") },
        { name: "x.exe", error: new Error("wrong type") },
      ],
    });

    expect(copy.title).toBe("Uploaded 1 of 3");
    expect(copy.body).toContain("big.pdf");
    expect(copy.body).toContain("x.exe");
  });
});
