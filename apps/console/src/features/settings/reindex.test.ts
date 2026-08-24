import { describe, expect, it } from "vitest";

import type { ProjectConfig } from "@/types/projects";

import { EMBEDDING_FIELDS, willReindex } from "./reindex";

const current = {
  embedding_provider: "google",
  embedding_model_name: "models/gemini-embedding-2",
  mrl_vector_size: null,
  temperature: 0.2,
  rag_top_k: 4,
} as unknown as ProjectConfig;

describe("EMBEDDING_FIELDS", () => {
  it("is exactly the three inputs to the embedding signature", () => {
    // sha256(f"{embedding_provider}|{embedding_model}|{mrl_vector_size or 'default'}")[:16]
    expect([...EMBEDDING_FIELDS].sort()).toEqual([
      "embedding_model_name",
      "embedding_provider",
      "mrl_vector_size",
    ]);
  });
});

describe("willReindex", () => {
  it("is false for an empty patch", () => {
    expect(willReindex({}, current)).toBe(false);
  });

  it("is false when only tuning fields change", () => {
    // Measured 2026-08-24: {"temperature":0.4,"rag_top_k":8} left the signature
    // at 71d147258a02c83c and the project active. This is what licenses the form
    // to save fourteen of the seventeen fields with no warning at all.
    expect(willReindex({ temperature: 0.9, rag_top_k: 8 }, current)).toBe(false);
  });

  it("is true when the vector size changes", () => {
    // The measured positive half: {"mrl_vector_size":768} moved the signature to
    // ae1c5f7850ecd307 and flipped the project to reindexing_required.
    expect(willReindex({ mrl_vector_size: 768 }, current)).toBe(true);
  });

  it("is true when the embedding provider changes", () => {
    expect(willReindex({ embedding_provider: "openai" }, current)).toBe(true);
  });

  it("is false when an embedding field is submitted UNCHANGED", () => {
    // A form that sends every field on save must not warn about all of them.
    expect(willReindex({ embedding_provider: "google" }, current)).toBe(false);
  });

  it("is true when clearing an embedding field that was set", () => {
    // Clearing falls through to the env default, which the browser cannot see --
    // so this MAY not re-embed. Warning anyway is the safe direction: a warning
    // that does not fire costs nothing, a missing one costs a silent re-embed.
    expect(willReindex({ embedding_provider: null }, current)).toBe(true);
  });

  it("is false when an already-unset field is submitted as null", () => {
    // `mrl_vector_size` is null in `current`. Clearing what is already clear is
    // not a change, and warning about it would fire on a form that sends nulls
    // for every untouched field.
    expect(willReindex({ mrl_vector_size: null }, current)).toBe(false);
  });

  it("treats a numeric field typed back as its own value as unchanged", () => {
    // The form reads inputs as strings and coerces with Number(), so a size the
    // user retyped identically arrives as a number, not a string. Guards against
    // a === comparison across types firing a spurious warning.
    expect(willReindex({ mrl_vector_size: 768 }, { ...current, mrl_vector_size: 768 })).toBe(false);
  });
});
