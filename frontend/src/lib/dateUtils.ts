/**
 * Shared date helpers — all display and filtering uses America/Los_Angeles.
 * DST is automatic: PDT in summer, PST in winter.
 */

export const LA_TZ = "America/Los_Angeles";

/**
 * Parse a SportMonks date string into a JS Date.
 * Handles all three formats SportMonks may return:
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
 * Returns "YYYY-MM-DD" in America/Los_Angeles.
 * Uses formatToParts (not a locale trick) so it works in every browser and Node version.
 */
export function toLADateStr(date: Date): string {
  if (isNaN(date.getTime())) return "invalid";
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: LA_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "00";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

/** Today's calendar date in LA ("YYYY-MM-DD") */
export function todayLA(): string {
  return toLADateStr(new Date());
}

/**
 * Tomorrow's calendar date in LA ("YYYY-MM-DD").
 * We add exactly 24 h to a noon-UTC anchor derived from today's LA date
 * so month/year rollovers are handled correctly by the JS Date engine.
 */
export function tomorrowLA(): string {
  const [y, m, d] = todayLA().split("-").map(Number);
  // noon UTC on today-in-LA: safely within the LA calendar day regardless of DST
  const anchor = new Date(Date.UTC(y, m - 1, d, 20, 0, 0)); // 20:00 UTC = noon PDT / 1 PM PST
  const next = new Date(anchor.getTime() + 24 * 60 * 60 * 1000);
  return toLADateStr(next);
}

/** "5:30 PM PDT" or "5:30 PM PST" — DST resolved automatically by Intl */
export function formatLATime(date: Date): string {
  if (isNaN(date.getTime())) return "—";
  return date.toLocaleTimeString("en-US", {
    timeZone: LA_TZ,
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

/** Returns true when the fixture date (LA calendar) is strictly after tomorrow. */
export function isUpcomingLA(date: Date): boolean {
  if (isNaN(date.getTime())) return false;
  return toLADateStr(date) > tomorrowLA();
}

/** "Saturday, May 16, 2026" */
export function formatLADateLong(date: Date): string {
  if (isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("en-US", {
    timeZone: LA_TZ,
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
export function formatLADateLabel(date: Date): string {
  if (isNaN(date.getTime())) return "—";
  const dStr = toLADateStr(date);
  if (dStr === todayLA()) return "TODAY";
  if (dStr === tomorrowLA()) return "TOMORROW";
  return date.toLocaleDateString("en-US", {
    timeZone: LA_TZ,
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
