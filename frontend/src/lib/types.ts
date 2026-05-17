export interface Team {
  id: number;
  name: string;
  logo?: string;
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
  predictedScore?: string;
  factors?: string[];
  riskFactors?: string[];
  comparison?: Record<string, unknown>;
  headToHead?: HeadToHead;
  recentFixtures?: unknown[];
}

export interface ApiResponse<T> {
  status: string;
  data: T;
  source?: string;
}
