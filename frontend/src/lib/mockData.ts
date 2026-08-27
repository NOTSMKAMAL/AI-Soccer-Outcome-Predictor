/**
 * MOCK FALLBACK ONLY.
 * Used in the frontend when the backend returns an empty fixture list or is unreachable.
 * The backend serves the same shape from football-data.org; these keep the
 * dashboard populated (flagged as preview data) when it is unreachable.
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
    id: "mock-pl-today-1",
    name: "Arsenal FC vs Chelsea FC",
    homeTeam: { id: 57, name: "Arsenal FC" },
    awayTeam: { id: 61, name: "Chelsea FC" },
    startingAt: fixtureAt(0, 9),    // 9 AM PDT today
    leagueId: 2021,
    leagueName: "Premier League",
    status: "finished",
    score: { home: 2, away: 1 },
    _isMock: true,
  },
  // Today — upcoming (prediction enabled)
  {
    id: "mock-pl-today-2",
    name: "Liverpool FC vs Manchester City FC",
    homeTeam: { id: 64, name: "Liverpool FC" },
    awayTeam: { id: 65, name: "Manchester City FC" },
    startingAt: fixtureAt(0, 12),   // 12 PM PDT today
    leagueId: 2021,
    leagueName: "Premier League",
    status: "upcoming",
    _isMock: true,
  },
  // Tomorrow — upcoming
  {
    id: "mock-pd-tmrw-1",
    name: "Real Madrid CF vs FC Barcelona",
    homeTeam: { id: 86, name: "Real Madrid CF" },
    awayTeam: { id: 81, name: "FC Barcelona" },
    startingAt: fixtureAt(1, 12),   // 12 PM PDT tomorrow
    leagueId: 2014,
    leagueName: "La Liga",
    status: "upcoming",
    _isMock: true,
  },
  {
    id: "mock-sa-tmrw-2",
    name: "FC Internazionale Milano vs AC Milan",
    homeTeam: { id: 108, name: "FC Internazionale Milano" },
    awayTeam: { id: 98, name: "AC Milan" },
    startingAt: fixtureAt(1, 11),   // 11 AM PDT tomorrow
    leagueId: 2019,
    leagueName: "Serie A",
    status: "upcoming",
    _isMock: true,
  },
];
