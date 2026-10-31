export interface Team {
  id: number;
  name: string;
}

export interface FixtureScore {
  home: number;
  away: number;
}

export interface Fixture {
  id: string;
  name: string;
  homeTeam: Team;
  awayTeam: Team;
  startingAt: string;
  leagueId: number;
  leagueName: string;
  status: string;
  score?: FixtureScore;
  venue?: string;
  _isMock?: boolean;
}

export interface H2HResult {
  name: string;
  date: string;
  result_info: string;
}

export interface HeadToHead {
  teamAWins: number;
  teamBWins: number;
  draws: number;
  total: number;
  recentResults?: H2HResult[];
}

export interface Prediction {
  winner: string;
  confidence: "low" | "medium" | "high" | string;
  reasoning: string;
  winProbability?: number;
  home_win_probability?: number;
  draw_probability?: number;
  away_win_probability?: number;
  predictedScore?: string;
  factors?: string[];
  riskFactors?: string[];
  comparison?: Record<string, unknown>;
  headToHead?: HeadToHead;
  recentFixtures?: unknown[];
}

/** What the signed-in user may still do today. `remaining` and `limit` are null when unlimited. */
export interface PredictionAllowance {
  unlimited: boolean;
  remaining: number | null;
  limit: number | null;
}

export interface ApiResponse<T> {
  status: string;
  data: T;
  source?: string;
}
