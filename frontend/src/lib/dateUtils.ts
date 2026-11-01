/**
 * Shared date helpers. All display and filtering uses the viewer's own time zone.
 *
 * `timeZone` stays undefined in the app, which means the browser's zone. The checks
 * in frontend/tests/dateUtils.test.mjs pass a zone and a clock so they are repeatable.
 * Labels stay in English to match the rest of the site, whatever the viewer's locale.
 */

const LOCALE = "en-US";

/**
 * Parse a football-data.org date string into a JS Date.
 * Handles all three formats football-data.org may return:
 *   "YYYY-MM-DD HH:MM:SS"   → no offset → treat as UTC
 *   "YYYY-MM-DD"            → bare date → midnight UTC
 *   ISO-8601 with T/offset  → passed through as-is
 */
export function parseFixtureDate(raw: string): Date {
  if (!raw) return new Date(NaN);
  if (raw.includes("T")) return new Date(raw);          // e.g. "2026-05-18T02:00:00Z"
  if (raw.includes(" ")) return new Date(raw.replace(" ", "T") + "Z"); // e.g. "2026-05-18 02:00:00"
  return new Date(raw + "T00:00:00Z");                  // e.g. "2026-05-18"
}

/**
 * Returns "YYYY-MM-DD" in the viewer's time zone.
 * Uses formatToParts (not a locale trick) so it works in every browser and Node version.
 */
export function toLocalDateStr(date: Date, timeZone?: string): string {
  if (isNaN(date.getTime())) return "invalid";
  const parts = new Intl.DateTimeFormat(LOCALE, {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "00";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

/** The viewer's calendar date ("YYYY-MM-DD") */
export function todayLocal(timeZone?: string, now: Date = new Date()): string {
  return toLocalDateStr(now, timeZone);
}

/**
 * The viewer's next calendar date ("YYYY-MM-DD").
 * Works on the date alone, so a 23- or 25-hour day at a clock change can't skip one.
 */
export function tomorrowLocal(timeZone?: string, now: Date = new Date()): string {
  const [y, m, d] = todayLocal(timeZone, now).split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + 1)).toISOString().slice(0, 10);
}

/** "5:30 PM PDT", or "5:30 PM GMT+9" where the zone has no common abbreviation in English */
export function formatLocalTime(date: Date, timeZone?: string): string {
  if (isNaN(date.getTime())) return "—";
  return date.toLocaleTimeString(LOCALE, {
    timeZone,
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

/** Returns true when the fixture's date is today or later on the viewer's calendar. */
export function isUpcomingLocal(date: Date, timeZone?: string, now: Date = new Date()): boolean {
  if (isNaN(date.getTime())) return false;
  return toLocalDateStr(date, timeZone) >= todayLocal(timeZone, now);
}

/** "Saturday, May 16, 2026" */
export function formatLocalDateLong(date: Date, timeZone?: string): string {
  if (isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(LOCALE, {
    timeZone,
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

/**
 * Label for the card center:
 * "TODAY" | "TOMORROW" | "Sat, May 17, 2026"
 */
export function formatLocalDateLabel(date: Date, timeZone?: string, now: Date = new Date()): string {
  if (isNaN(date.getTime())) return "—";
  const day = toLocalDateStr(date, timeZone);
  if (day === todayLocal(timeZone, now)) return "TODAY";
  if (day === tomorrowLocal(timeZone, now)) return "TOMORROW";
  return date.toLocaleDateString(LOCALE, {
    timeZone,
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/** The next daily prediction reset: 00:00 UTC, when backend/access.py starts a new day. */
export function nextDailyReset(now: Date = new Date()): Date {
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1));
}

/** When the limit resets, for the viewer: "today at 5:00 PM PDT" or "tomorrow at 9:00 AM GMT+9". */
export function formatDailyReset(timeZone?: string, now: Date = new Date()): string {
  const reset = nextDailyReset(now);
  const day = toLocalDateStr(reset, timeZone) === todayLocal(timeZone, now) ? "today" : "tomorrow";
  return `${day} at ${formatLocalTime(reset, timeZone)}`;
}
