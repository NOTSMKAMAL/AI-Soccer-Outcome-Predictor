const LEAGUE_ACCENTS: Record<string, string> = {
  "Major League Soccer":   "#E82E2E",
  "MLS":                   "#E82E2E",
  "Premier League":        "#9381FF",
  "La Liga":               "#EE8707",
  "Serie A":               "#4A9FFF",
  "Bundesliga":            "#E82E2E",
  "Ligue 1":               "#4A9FFF",
  "Champions League":      "#F8C25C",
  "UEFA Champions League": "#F8C25C",
};

export const DEFAULT_LEAGUE_ACCENT = "#13BBAF";

/** Accent colour for a league, matched case-insensitively by substring; falls back to the default teal. */
export function getLeagueAccent(leagueName: string): string {
  const key = Object.keys(LEAGUE_ACCENTS).find((k) =>
    leagueName?.toLowerCase().includes(k.toLowerCase())
  );
  return key ? LEAGUE_ACCENTS[key] : DEFAULT_LEAGUE_ACCENT;
}
