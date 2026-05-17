/**
 * MOCK FALLBACK ONLY.
 * Used in the frontend when the backend returns an empty fixture list or is unreachable.
 * Remove this file once the backend /api/fixtures endpoint returns real SportMonks data.
 */
import type { Fixture } from "./types";

// Returns an ISO string for the given day offset (0 = today) at the given LA hour.
// DST-safe: verifies the UTC→LA conversion rather than using a hardcoded offset.
const fixtureAt = (offsetDays: number, laHour: number): string => {
  const now = new Date();
  const laDateStr = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles",
    year: "numeric", month: "2-digit", day: "2-digit",
  }).format(now);
  const [m, d, y] = laDateStr.split("/").map(Number);
  // Try PDT (UTC-7) then PST (UTC-8), pick whichever round-trips correctly.
  for (const offset of [7, 8]) {
    const candidate = new Date(Date.UTC(y, m - 1, d + offsetDays, laHour + offset, 0, 0));
    const actual = parseInt(
      new Intl.DateTimeFormat("en-US", {
        timeZone: "America/Los_Angeles", hour: "2-digit", hour12: false,
      }).format(candidate),
      10,
    );
    if (actual === laHour) return candidate.toISOString();
  }
  // Fallback — should never reach here for valid laHour values
  return new Date(Date.UTC(y, m - 1, d + offsetDays, laHour + 7, 0, 0)).toISOString();
};

export const MOCK_FIXTURES: Fixture[] = [
  // Today — finished (shows score)
  {
    id: "mock-mls-today-1",
    name: "LA Galaxy vs LAFC",
    homeTeam: { id: 246, name: "LA Galaxy" },
    awayTeam: { id: 1436, name: "LAFC" },
    startingAt: fixtureAt(0, 14),   // 2 PM PDT today
    leagueId: 779,
    leagueName: "MLS",
    status: "finished",
    score: { home: 2, away: 1 },
    _isMock: true,
  },
  // Today — upcoming (prediction enabled)
  {
    id: "mock-mls-today-2",
    name: "Inter Miami CF vs Atlanta United",
    homeTeam: { id: 14163, name: "Inter Miami CF" },
    awayTeam: { id: 13847, name: "Atlanta United" },
    startingAt: fixtureAt(0, 19),   // 7 PM PDT today
    leagueId: 779,
    leagueName: "MLS",
    status: "upcoming",
    _isMock: true,
  },
  // Tomorrow — upcoming
  {
    id: "mock-mls-tmrw-1",
    name: "Seattle Sounders vs Portland Timbers",
    homeTeam: { id: 13862, name: "Seattle Sounders" },
    awayTeam: { id: 13868, name: "Portland Timbers" },
    startingAt: fixtureAt(1, 17),   // 5 PM PDT tomorrow
    leagueId: 779,
    leagueName: "MLS",
    status: "upcoming",
    _isMock: true,
  },
  {
    id: "mock-mls-tmrw-2",
    name: "NYC FC vs Red Bull New York",
    homeTeam: { id: 13869, name: "NYC FC" },
    awayTeam: { id: 347, name: "Red Bull New York" },
    startingAt: fixtureAt(1, 20),   // 8 PM PDT tomorrow
    leagueId: 779,
    leagueName: "MLS",
    status: "upcoming",
    _isMock: true,
  },
];
