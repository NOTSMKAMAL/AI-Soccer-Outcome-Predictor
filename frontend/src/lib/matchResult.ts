export type MatchResult = "W" | "D" | "L";

/**
 * Result from one team's side, given its own goals and the opponent's.
 * Returns null when either score is missing, so callers show nothing rather
 * than guess. Compare scores, never team names: names share short words
 * ("Le Havre AC" vs "Olympique de Marseille" both contain "le").
 */
export function resultFromScores(
  ownGoals: number | null | undefined,
  opponentGoals: number | null | undefined,
): MatchResult | null {
  if (ownGoals == null || opponentGoals == null) return null;
  if (ownGoals > opponentGoals) return "W";
  if (ownGoals < opponentGoals) return "L";
  return "D";
}
