import { describe, expect, it } from "vitest";

import { rank, score } from "./filter";

const item = (label: string, group = "Go to", keywords?: string) => ({ label, group, keywords });

describe("score", () => {
  it("returns 0 for an empty query, so every command survives the initial render", () => {
    expect(score("", item("New project"))).toBe(0);
    expect(score("   ", item("New project"))).toBe(0);
  });

  it("ranks a prefix above a word prefix above a substring above a subsequence", () => {
    const prefix = score("new", item("New project"))!;
    const word = score("pro", item("New project"))!;
    const substring = score("w pro", item("New project"))!;
    const subsequence = score("npro", item("New project"))!;
    expect(prefix).toBeGreaterThan(word);
    expect(word).toBeGreaterThan(substring);
    expect(substring).toBeGreaterThan(subsequence);
  });

  it("matches a subsequence, which is the whole reason this is not `includes`", () => {
    expect(score("npj", item("New project"))).not.toBeNull();
  });

  it("does not match when a letter is missing", () => {
    expect(score("zzz", item("New project"))).toBeNull();
  });

  it("searches the group and the keywords, not only the label", () => {
    expect(score("account", item("Sign out", "Account"))).not.toBeNull();
    expect(score("logout", item("Sign out", "Account", "logout exit"))).not.toBeNull();
  });

  it("matches keywords as substrings, not as subsequences", () => {
    // The looser rule would be actively worse: a subsequence over a keyword bag
    // matches nearly every query, so the alias has to be spelled the way a user
    // would type it. "log out" does not answer "logout"; "logout" does.
    expect(score("logout", item("Sign out", "Account", "log out exit"))).toBeNull();
  });

  it("is case-insensitive on both sides", () => {
    expect(score("NEW", item("new project"))).not.toBeNull();
  });
});

describe("rank", () => {
  it("puts the shorter label first inside one band", () => {
    const result = rank("set", [item("Settings for this project"), item("Settings")]);
    expect(result[0].label).toBe("Settings");
  });

  it("keeps the authored order when the query is empty", () => {
    const items = [item("One"), item("Two"), item("Three")];
    expect(rank("", items).map((i) => i.label)).toEqual(["One", "Two", "Three"]);
  });

  it("drops everything that does not match", () => {
    expect(rank("qqqq", [item("One"), item("Two")])).toEqual([]);
  });
});
