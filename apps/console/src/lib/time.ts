/**
 * Relative timestamps for list rows.
 *
 * DISPLAY ONLY. Nothing in this console may branch on the difference between the
 * server's clock and the browser's -- F6 established that after a poll deadline
 * computed from `updated_at` compared the two and got it wrong. A label is safe
 * where a deadline is not, and the clamp below is what keeps it safe: a server
 * running a few seconds ahead would otherwise render "in 4 seconds" on a row the
 * user just created, which reads as a bug in the app rather than as clock skew.
 *
 * SQLite writes `datetime('now')` -- "2026-08-29 06:14:41", with a space and no
 * zone -- which `new Date()` parses as LOCAL time on some engines and rejects on
 * others, where Postgres returns a zoned ISO string. Normalised here rather than
 * at each call site, because a wrong-by-hours timestamp looks like real data.
 */
const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export function parseTimestamp(value: string | null | undefined): Date | null {
  if (!value) return null;
  // A bare "YYYY-MM-DD HH:MM:SS" carries no zone and is UTC on both stores.
  const normalised = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/.test(value)
    ? `${value.replace(" ", "T")}Z`
    : value;
  const date = new Date(normalised);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function relativeTime(value: string | null | undefined, now = Date.now()): string {
  const date = parseTimestamp(value);
  if (!date) return "";

  // Clamped at zero: see the note above on clock skew.
  const elapsed = Math.max(0, now - date.getTime());

  if (elapsed < MINUTE) return "just now";
  if (elapsed < HOUR) return `${Math.floor(elapsed / MINUTE)}m ago`;
  if (elapsed < DAY) return `${Math.floor(elapsed / HOUR)}h ago`;
  if (elapsed < 7 * DAY) return `${Math.floor(elapsed / DAY)}d ago`;

  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** The full timestamp, for a `title` attribute beside the relative one. */
export function absoluteTime(value: string | null | undefined): string | undefined {
  return parseTimestamp(value)?.toLocaleString();
}
