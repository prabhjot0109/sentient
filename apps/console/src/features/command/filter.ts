/**
 * Ranking for the command palette.
 *
 * Pure, and in its own module, because this is the part with judgement in it:
 * the component around it is an input and a list. It is a SUBSEQUENCE match, not
 * a substring one -- "npro" has to reach "New project" -- but a subsequence match
 * alone ranks badly, since every long label contains almost every short query
 * somewhere. So a match is scored by HOW it matched, and the score is what
 * orders the list.
 *
 * The subsequence rule applies to the LABEL only. Group and `keywords` are
 * matched as substrings, because a subsequence over a bag of alias words matches
 * very nearly every query -- so an alias has to be written the way a user would
 * actually type it ("logout", not "log out").
 */
export type Rankable = { label: string; group: string; keywords?: string };

/** Highest first. The bands are ordered by how much of the query the user had to trust. */
const EXACT_PREFIX = 4000;
const WORD_PREFIX = 3000;
const SUBSTRING = 2000;
const SUBSEQUENCE = 1000;

function isSubsequence(query: string, text: string): boolean {
  let index = 0;
  for (const character of text) {
    if (character === query[index]) index += 1;
    if (index === query.length) return true;
  }
  return query.length === 0;
}

/** `null` when it does not match at all, so the caller filters and sorts in one pass. */
export function score(query: string, item: Rankable): number | null {
  const q = query.trim().toLowerCase();
  if (!q) return 0;

  const label = item.label.toLowerCase();
  const haystack = `${label} ${item.group.toLowerCase()} ${(item.keywords ?? "").toLowerCase()}`;

  // Shorter labels win inside a band: with "set", "Settings" should outrank
  // "Speech settings note", and both matched the same way.
  const brevity = Math.max(0, 100 - item.label.length);

  if (label.startsWith(q)) return EXACT_PREFIX + brevity;
  if (label.split(/[\s/·-]+/).some((word) => word.startsWith(q))) return WORD_PREFIX + brevity;
  if (haystack.includes(q)) return SUBSTRING + brevity;
  if (isSubsequence(q, label)) return SUBSEQUENCE + brevity;
  return null;
}

export function rank<T extends Rankable>(query: string, items: T[]): T[] {
  return (
    items
      .map((item) => ({ item, points: score(query, item) }))
      .filter((entry): entry is { item: T; points: number } => entry.points !== null)
      // A stable sort, which ES2019 guarantees, is what keeps the declared order
      // inside a band -- so an empty query renders the groups as authored.
      .sort((a, b) => b.points - a.points)
      .map((entry) => entry.item)
  );
}
