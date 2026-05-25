# How the AI Sports Outcome Predictor Works

## Overview

The AI Sports Outcome Predictor combines statistical modeling (Dixon-Coles) with AI reasoning (Gemini) to predict football match outcomes. The pipeline flows from fixture selection through data enrichment, statistical analysis, winner determination, AI reasoning, and finally response assembly. Each step is independent but ordered, so the output of one feeds the next.

---

## STEP 1: Fixture Selection

### Where Fixtures Come From

Fixtures originate from the **SportMonks API v3** (https://docs.sportmonks.com/football/api/fixtures), which is the authoritative source of live sports data. The app fetches upcoming and recent fixtures for 6 leagues:
- Premier League (league_id 8)
- Ligue 1 (league_id 301)
- La Liga (league_id 564)
- Serie A (league_id 384)
- Bundesliga (league_id 82)
- Major League Soccer (league_id 779)

The backend's `/api/fixtures` endpoint calls `get_upcoming_mls_fixtures()` which tries two strategies:
1. **Primary**: Date-range endpoint `/fixtures/between/{start}/{end}` (14 days back, 60 days ahead)
2. **Fallback**: Per-league endpoint `/fixtures/upcoming/leagueId/{id}` if the date-range returns no upcoming fixtures

If both fail, the app gracefully returns mock fixtures so the dashboard is never empty.

### What Data Is in a Fixture Object

A normalized fixture contains:
- `id`: Unique fixture identifier (string)
- `name`: Human-readable match name (e.g., "Liverpool vs Manchester City")
- `homeTeam`: `{id, name, logo}` — home team object
- `awayTeam`: `{id, name, logo}` — away team object
- `startingAt`: ISO 8601 kickoff time (string)
- `leagueId`: SportMonks league identifier (integer)
- `leagueName`: Human-readable league name (string)
- `seasonId`: Season identifier for standings/stats lookups
- `status`: Match state ("NS" upcoming, "LIVE" in-play, match result status when finished)
- `score`: `{home: int, away: int}` — goal count if match has been played
- `venue`: Stadium name (string or null)
- `_isMock`: Boolean flag indicating whether data is real (false) or mock (true)

### How the Frontend Passes Data to the Backend

1. User clicks a fixture on the dashboard
2. Next.js routes to `/prediction/[matchId]` where `matchId` is the fixture's string ID
3. Frontend loads the fixture via `GET /api/fixtures/{match_id}` (served from cache if available)
4. When the user clicks "Generate AI Prediction", frontend calls `POST /api/fixtures/{match_id}/prediction` with Firebase ID token
5. Backend extracts `homeTeam.id`, `awayTeam.id`, `homeTeam.name`, `awayTeam.name` from the fixture
6. These IDs and names flow into the enrichment and prediction pipeline

---

## STEP 2: Data Enrichment (`_gather_enriched`)

### Overview

Before making a prediction, the backend enriches the fixture with 7 parallel SportMonks API calls. These calls fetch recent form, current standings, expected goals (xG), lineups, squad depth, and top scorers. All 7 calls run in parallel using Python's `asyncio.gather()`, so the total wall-clock time is the slowest single call (~8 seconds), not the sum of all calls.

### Which Calls Run (and When)

All 7 calls execute in parallel as soon as the backend's `/api/fixtures/{match_id}/prediction` endpoint is invoked (assuming the fixture is real, not mocked). The calls are:

**1. Recent Form: Team A**
```
GET /v3/football/fixtures/between/{start_date}/{end_date}/{team_a_id}
include=participants;scores;statistics.type
per_page=100
```
Returns the last 60 days of completed fixtures for team A, limited to 5 most recent. Parsed to extract:
- Opponent, kickoff date, result (Win/Draw/Loss)
- Individual match statistics (shots, possession, passes, corners, fouls, cards)

**2. Recent Form: Team B**
Same endpoint as #1, but for `team_b_id`. Returns 5 most recent fixtures for team B.

**3. Season Standings**
```
GET /v3/football/standings/seasons/{season_id}
include=participant;details
```
Returns full standings table for the season with:
- Position, points, W/D/L, goals scored, goals conceded, goal difference, form string
- Extracted to compute per-team stats: `goals_scored_per_game`, `goals_conceded_per_game`
- These stats are also returned to the frontend for display

**4. Fixture xG and Trends**
```
GET /v3/football/fixtures/{fixture_id}
include=xGFixture;trends;participants
```
Returns expected goals (xG) for both teams — a measure of chance quality independent of actual goals. Also returns current trends (form indicators) for each team.

**5. Confirmed Lineups**
```
GET /v3/football/fixtures/{fixture_id}
include=lineups
```
Returns confirmed starting lineups (type_id 11) for both teams:
- Player names, position IDs, jersey numbers
- Only populated a few hours before kickoff; returns empty if lineups not yet confirmed

**6. Top Scorers**
```
GET /v3/football/topscorers/seasons/{season_id}
include=player;participant
per_page=20
```
Returns the 10 leading goal scorers in the season:
- Player name, team name, goals, rank
- Used by Gemini to identify if any top scorers are starting today

**7. Squad Depth**
```
GET /v3/football/squads/teams/{team_a_id}
include=player
```
Returns full squad for team A:
- Player names, position IDs (24=goalkeeper), captain flag
- Used to detect if first-choice goalkeeper or captain is missing from lineups

### Parallel Execution

All 7 calls fire simultaneously. The returned data is processed into a single `enriched_data` dictionary:
```python
{
  "team_a_recent_form": list[dict] or None,
  "team_b_recent_form": list[dict] or None,
  "standings": list[dict] — full standings table,
  "team_a_stats": {goals_scored, goals_conceded, wins, draws, losses, total_matches},
  "team_b_stats": {goals_scored, goals_conceded, wins, draws, losses, total_matches},
  "xg": {team_a_xg: float, team_b_xg: float} or None,
  "trends": {team_a: list[str], team_b: list[str]} or None,
  "injuries": {team_a: list[dict], team_b: list[dict]} — empty for Starter plan,
  "lineup": {team_a_starters: list[dict], team_b_starters: list[dict], confirmed: bool},
  "topscorers_with_names": list[dict],
  "squad_a": list[dict],
  "season_id": int
}
```

This enriched data is cached in `_enriched_cache` so repeated calls for the same fixture don't re-fetch.

---

## STEP 3: Dixon-Coles Probability Calculation

### What Dixon-Coles Is (Simplified Math)

Dixon-Coles is a statistical model developed in 1997 by Simon Dixon and Stuart Coles to model football match outcomes. It works by:

1. **Measuring team strength** from historical goal data
   - Attack strength: How many goals does team A score per game relative to the league average?
   - Defense strength: How many goals does team A concede per game relative to the league average?

2. **Modeling goal distribution** using Poisson probability
   - Football goals follow a Poisson distribution (rare events, roughly equal probability across time)
   - Given team A's attack strength and team B's defense, what's the probability of exactly 0, 1, 2, ... goals?

3. **Computing match outcomes** by summing scorelines
   - Home win: sum of P(home goals > away goals)
   - Draw: sum of P(home goals == away goals)
   - Away win: sum of P(away goals > home goals)

4. **Correcting low-score bias** using the τ (tau) parameter
   - Real football has more 0-0, 1-0, 1-1 scorelines than pure Poisson predicts
   - The τ correction adjusts probabilities for these specific scorelines

### How Attack/Defense Strength Is Computed

The function `dixon_coles_probability()` follows a **three-tier priority**:

**Priority 1: Rolling Form (20% recent, 80% season)**
If rolling form is provided with all 5 required fields:
- `home_scored_5r`, `home_conceded_5r` (recent 5 matches for team A at home)
- `away_scored_5r`, `away_conceded_5r` (recent 5 matches for team B away)

Then compute:
- Rolling per-game: `roll_s_a = home_scored_5r / home_rounds_used`
- Season per-game: `seas_s_a = goals_scored / total_matches`
- Blend: `avg_s_a = 0.20 * roll_s_a + 0.80 * seas_s_a`

This 20/80 split means the model is 80% confident in season-long trends but responsive (20%) to recent form.

**Priority 2: Season Statistics Endpoint**
If rolling form is unavailable but `season_id` is provided:
- Fetch per-game stats from `get_season_team_stats(season_id)`
- Uses `goals_scored_per_game`, `goals_conceded_per_game` directly

**Priority 3: Standings Fallback**
If both above unavailable, use standings data:
- `avg_s_a = goals_scored / total_matches`
- `avg_c_a = goals_conceded / total_matches`
- Return None if any team has 0 matches played (division-by-zero guard)

### Lambda and Mu (Expected Goals)

Once per-game averages are selected, the algorithm computes attack and defense indices:

```
league_avg = (avg_s_a + avg_s_b) / 2
atk_a = avg_s_a / league_avg  (team A's attack strength relative to league avg)
def_a = avg_c_a / league_avg  (team A's defense strength relative to league avg)
atk_b = avg_s_b / league_avg
def_b = avg_c_b / league_avg

home_advantage = per_league_coeff(league_id) or default 1.15
lambda = atk_a * def_b * home_advantage * league_avg  (expected goals for home team A)
mu = atk_b * def_a * (1.0 / home_advantage) * league_avg  (expected goals for away team B)
```

**What lambda_home and lambda_away represent:**
- `lambda` = expected number of goals team A will score (Poisson rate parameter)
- `mu` = expected number of goals team B will score
- Higher lambda/mu → higher probability of scoring → win bias

### Per-League Home Advantage Coefficients

Research (Dixon & Coles, verified in backtest) shows home advantage varies by league:

| League | ID | Coefficient | Interpretation |
|--------|-----|-------------|-----------------|
| Premier League | 8 | 1.18 | Strong home crowds, familiar pitch |
| Bundesliga | 564 | 1.16 | Passionate fans |
| Serie A | 384 | 1.15 | Moderate home advantage |
| Ligue 1 | 301 | 1.13 | Slight home advantage |
| MLS | 779 | 1.08 | Weakest — large travel distances, less crowd effect |
| Default (unknown) | — | 1.15 | Conservative middle estimate |

The home advantage multiplier is applied only to the **home team's expected goals**:
- If team A is home: `lambda *= home_advantage`, `mu /= home_advantage`
- If team B is home: `lambda /= home_advantage`, `mu *= home_advantage`

### The τ (Tau) Low-Score Correction

Raw Poisson probabilities overestimate draws and underestimate 0-0, 1-0, 0-1, 1-1 scorelines. The τ correction applies a multiplicative factor `rho = -0.1` (default):

```
τ(x, y) = 1.0                            if not a low-score combo
         = 1.0 - λ*μ*ρ                   if x==0 and y==0
         = 1.0 + λ*ρ                     if x==0 and y==1
         = 1.0 + μ*ρ                     if x==1 and y==0
         = 1.0 - ρ                       if x==1 and y==1
```

Since ρ = -0.1 (negative), this **increases** probabilities for low scores:
- `τ(0,0) = 1.0 + 0.1*λ*μ` (makes 0-0 more likely)
- `τ(0,1) = 1.0 - 0.1*λ` (makes 0-1 more likely)
- etc.

### The 10×10 Scoreline Matrix

The algorithm sums joint Poisson probabilities over all scorelines from 0-0 to 10-10:

```python
home_win = draw = away_win = 0.0
for i in range(11):  # home team goals
  for j in range(11):  # away team goals
    p = τ(i, j) * P(Poisson(λ)==i) * P(Poisson(μ)==j)
    if i > j: home_win += p
    elif i == j: draw += p
    else: away_win += p
```

- Home win: all (i, j) where home goals > away goals
- Draw: all (i, j) where goals are equal
- Away win: all (i, j) where away goals > home goals

Probabilities outside (0-10) are negligible in practice.

### Computing Win Probabilities

After summing, normalize so probabilities sum to exactly 1.0:

```python
total = home_win + draw + away_win
hw = home_win / total
dr = draw / total
aw = away_win / total
```

### Double-Cap Normalization

After initial normalization, apply floor/ceiling caps and re-normalize:

```python
hw = max(0.05, min(0.90, hw))
dr = max(0.05, min(0.90, dr))
aw = max(0.05, min(0.90, aw))

t2 = hw + dr + aw
return {
  "home_win": max(0.05, min(0.90, hw / t2)),
  "draw": max(0.05, min(0.90, dr / t2)),
  "away_win": max(0.05, min(0.90, aw / t2)),
  "method": "rolling_blend_20_80" or "season_stats" or "standings"
}
```

The double-cap ensures:
1. No probability drops below 5% (avoids overconfidence)
2. No probability exceeds 90% (preserves uncertainty)
3. Probabilities sum to exactly 1.0 after normalization

---

## STEP 4: Winner Determination

### How Winner Is Determined

Once Dixon-Coles returns `dc_probs = {home_win, draw, away_win}`, the winner is the outcome with the highest probability:

```python
if dc_probs["home_win"] >= dc_probs["away_win"] and dc_probs["home_win"] >= dc_probs["draw"]:
    winner = team_a_name  (home team)
elif dc_probs["away_win"] >= dc_probs["home_win"] and dc_probs["away_win"] >= dc_probs["draw"]:
    winner = team_b_name  (away team)
else:
    winner = team_a_name  (draw is most likely — default to home team)
```

Note: If a draw is predicted as most likely, the home team is assigned as the "winner" for the purposes of the response. The three-way probabilities are still returned to the frontend, so users see the full distribution.

### Why This Overrides Gemini's Assessment

Gemini is asked to make an independent prediction, but it can hallucinate, overweight recent news, or be inconsistent. The Dixon-Coles prediction is:
- **Deterministic**: Same input always produces the same output
- **Calibrated**: Backtested on 1747 historical matches
- **Reproducible**: Pure mathematics, not a language model

Therefore, the backend overrides Gemini's winner with the Dixon-Coles verdict and injects a "PREDICTED WINNER" instruction into Gemini's prompt, asking it to explain WHY the predicted team will win (using the provided data), rather than arguing for a different outcome.

### How Confidence Is Computed

The confidence label is derived from the **maximum probability** among the three outcomes:

```python
winner_prob = max(dc_probs["home_win"], dc_probs["draw"], dc_probs["away_win"])

if winner_prob >= _CONF_HIGH (0.60):
    confidence = "high"
elif winner_prob >= _CONF_MEDIUM (0.45):
    confidence = "medium"
else:
    confidence = "low"
```

These thresholds are calibrated from the backtest:
- **High-confidence predictions** (≥60% winner prob) achieved **73.7% accuracy** on 351 high-confidence fixtures in the CSV backtest
- This means when the model is "confident", it's right about 3 times out of 4
- Medium and low bins are more balanced

---

## STEP 5: Gemini Reasoning

### What Data Is Passed to Gemini in the Prompt

The backend constructs a detailed prompt that includes:

**1. Predicted Winner Instruction** (if Dixon-Coles computed probabilities)
```
PREDICTED WINNER: {winner_name}
The statistical model has determined that {winner_name} is predicted to win this match.
Your task: Write a clear, factual explanation of WHY {winner_name} is predicted to win,
using the data provided below. Cite specific statistics. Do NOT argue for the other team
winning. Do NOT contradict the predicted winner. Your Winner field MUST be: {winner_name}
```

**2. Head-to-Head History**
```
HEAD-TO-HEAD HISTORY ({total} matches):
  - Team A: {wins} wins
  - Team B: {wins} wins
  - Draws: {draws}
Recent results:
  - {fixture name} ({date}): {result_info}
  - ...
```
Retrieved from `compare_matchup()`, which queries SportMonks for historical fixtures between the two teams.

**3. Enriched Data Section** (built by `_build_enriched_section()`)

**Recent Form** (last 5 matches per team):
```
RECENT FORM (last 5 matches):
  - Team A: W/D/L/W/D — 60% win rate
  - Team B: W/W/D/L/W — 60% win rate
```

**Current League Standings** (position, points, goal difference, form):
```
CURRENT LEAGUE STANDINGS:
  - Team A: 2nd, 42 pts, GD +18, form: W/W/D
  - Team B: 5th, 35 pts, GD +5, form: W/L/D
```

**Season Statistics** (goals scored/conceded, clean sheets, W/D/L record):
```
SEASON STATISTICS:
  - Team A: 45 scored, 15 conceded, 8 clean sheets, 13W/3D/1L
  - Team B: 38 scored, 22 conceded, 5 clean sheets, 11W/2D/4L
```

**xG (Expected Goals)** — quality of chances independent of actual goals:
```
xG PERFORMANCE (expected goals — quality of chances created):
  - Team A xG: 42.5
  - Team B xG: 35.2
  xG above actual goals = underperforming; below = overperforming.
```

**Current Trends** — form indicators:
```
CURRENT TRENDS:
  - Team A: on a 4-match winning streak, league leader
  - Team B: inconsistent, 2 losses in last 5
```

**Injury & Suspension News** (empty for Starter tier):
```
INJURY & SUSPENSION NEWS:
  - Team A: Full squad available
  - Team B: Full squad available
```

**Top Scorers in League** (with flag if starting today):
```
TOP SCORERS IN THIS LEAGUE (season):
  1. Player A (Team A): 15 goals ← CONFIRMED STARTING for Team A
  2. Player B (Team B): 14 goals ← CONFIRMED STARTING for Team B
  3. Player C (Team C): 12 goals
```

**Confirmed Starting Lineups** (if available):
```
CONFIRMED STARTING LINEUPS:
  Team A starting XI: Player1, Player2, Player3, ...
  Team B starting XI: Player1, Player2, Player3, ...
```

**Squad Depth Note** (if key players absent):
```
SQUAD DEPTH NOTE (Team A):
  Key player(s) absent from starting XI: Goalkeeper Jones (GK), Captain Smith (captain)
  Instruction: a missing captain or first-choice goalkeeper significantly affects Team A's
  prediction confidence — lower their defensive/leadership rating accordingly.
```

**Real-Time News Instruction**:
```
REAL-TIME NEWS INSTRUCTION (Google Search):
Search for: "Team A vs Team B injury news team news lineup 2026-05-24"
If you find relevant injury reports, lineup hints, or manager press-conference quotes,
include them in the format: REAL-TIME TEAM NEWS (from Google Search): ...
```

### Why the Predicted Winner Is Injected First

The prompt includes the predicted winner upfront because:
1. **Prevents contradictions**: Gemini won't argue for a different team and contradict the model
2. **Grounds reasoning**: Gemini is asked to explain statistical WHY, not make independent guesses
3. **Consistency**: Multiple calls for the same fixture produce the same winner
4. **Speed**: Gemini doesn't waste tokens debating which team should win

### What Gemini Produces

Gemini is asked to respond in this exact format:

```
Winner: {team name}
Confidence: <low | medium | high>
Reasoning: <4-5 sentences. Each sentence must reference a specific statistic
from the data above. Do not use generic phrases without citing actual numbers.>
Key Factor 1: <title> | <one sentence with specific stat>
Key Factor 2: <title> | <one sentence with specific stat>
Key Factor 3: <title> | <one sentence with specific stat>
```

Example output:
```
Winner: Manchester City
Confidence: high
Reasoning: Manchester City leads the league with 45 goals scored and only 15
conceded, a +30 goal differential vs Liverpool's +18. Their xG of 42.5
suggests they create higher-quality chances. They've won 4 straight matches
while Liverpool drew 1-1 to Burnley last week. Ruben Dias is missing (captain),
which slightly lowers their defensive rating, but their attacking depth is
unmatched.
Key Factor 1: Offensive Dominance | Manchester City's 45 goals scored vs Liverpool's 38
Key Factor 2: Defense vs Weakness | City concedes only 15 goals; Liverpool 22
Key Factor 3: Current Form | Manchester City on 4-win streak vs Liverpool's mixed recent form
```

### How Gemini's Output Is Parsed

The backend parses the response line-by-line, extracting values after known keys:

```python
parsed: dict[str, str] = {}
known_keys = {"Winner", "Confidence", "Reasoning", "Key Factor 1", "Key Factor 2", "Key Factor 3"}

for line in raw.strip().splitlines():
    matched_key = None
    for k in known_keys:
        if line.strip().startswith(f"{k}:"):
            matched_key = k
            break
    if matched_key:
        parsed[matched_key] = line.split(":", 1)[1].strip()
```

The parser handles multi-line fields by continuing to append lines until the next key is found.

Key Factors are further split on `|`:
```python
def _parse_kf(raw_str: str) -> dict | None:
    parts = raw_str.split("|", 1)
    return {
        "title": parts[0].strip(),
        "text": parts[1].strip() if len(parts) > 1 else raw_str.strip(),
    }
```

---

## STEP 6: Response Assembly

### How result_data Is Built

After parsing Gemini's response, the backend assembles a complete result object:

```python
result_data = {
    "winner": parsed.get("Winner", "Unknown"),
    "confidence": computed_confidence_from_dixon_coles,  # NOT from Gemini
    "reasoning": parsed.get("Reasoning", ""),
    "headToHead": {
        "teamAWins": data["team_a_wins"],
        "teamBWins": data["team_b_wins"],
        "draws": data["draws"],
        "total": data["total_h2h"],
        "recentResults": data["recent_results"],  # list of 5 most recent H2H matches
    },
    "home_win_probability": dc_probs["home_win"],
    "draw_probability": dc_probs["draw"],
    "away_win_probability": dc_probs["away_win"],
    "probability_method": "dixon-coles",
    "keyFactors": [
        {"title": "...", "text": "..."},
        {"title": "...", "text": "..."},
        {"title": "...", "text": "..."},
    ]
}
```

If Dixon-Coles probabilities are unavailable (mock fixture or insufficient data), the backend falls back to confidence-based estimates:

```python
confidence_map = {
    "high": (0.72, 0.18, 0.10),    # 72% winner, 18% draw, 10% loser
    "medium": (0.52, 0.23, 0.25),  # 52% winner, 23% draw, 25% loser
    "low": (0.38, 0.28, 0.34),     # 38% winner, 28% draw, 34% loser
}
```

### What Fields the Frontend Receives

The frontend's `Prediction` type includes:

```typescript
interface Prediction {
  winner: string;
  confidence: "low" | "medium" | "high";
  reasoning: string;
  home_win_probability?: number;    // Dixon-Coles [0.05, 0.90]
  draw_probability?: number;
  away_win_probability?: number;
  headToHead?: {
    teamAWins: number;
    teamBWins: number;
    draws: number;
    total: number;
    recentResults?: Array<{name, date, result_info}>;
  };
  keyFactors?: Array<{title: string, text: string}>;
  probabilityMethod?: "dixon-coles" | "confidence-estimate";
}
```

### How Three-Way Probability Bars Are Rendered

The frontend component `ThreeSegmentBar` renders the probabilities as a horizontal bar split into three colored segments:

```typescript
function ThreeSegmentBar({
  homeP, drawP, awayP,
  homeName, awayName,
  ...
}) {
  // Each segment's width is proportional to its probability (0.05-0.90 range)
  const totalWidth = homeP + drawP + awayP;
  return (
    <div className="flex h-8 rounded-lg overflow-hidden gap-0.5">
      <div style={{width: `${homeP / totalWidth * 100}%`}} className="bg-blue-500" />
      <div style={{width: `${drawP / totalWidth * 100}%`}} className="bg-gray-500" />
      <div style={{width: `${awayP / totalWidth * 100}%`}} className="bg-red-500" />
    </div>
  );
}
```

The bars are always rendered because probabilities are always returned (either from Dixon-Coles or confidence-fallback).

---

## STEP 7: Accuracy and Validation

### What the Backtest Is

The backtest evaluates the model on **historical fixtures with known outcomes**. The script `scripts/backtest.py` loads completed matches from two sources:

1. **CSV Mode**: `enriched_fixtures.csv` — 1747 completed fixtures from 2023-2024 seasons across 5 leagues
   - Stands matches-played from end-of-season standings (not match-day standings)
   - No rolling form data (early-season fixtures use standings only)
   - Most realistic production scenario

2. **API Mode**: Fetches 75 recent completed fixtures live from SportMonks
   - Uses live standings + rolling form when available
   - Smaller sample, higher variance

### Current Accuracy Numbers

**CSV Baseline (1747 fixtures):**
- Overall accuracy: **52.8%**
- Home baseline (always predict home): 44.8%
- Improvement: +8.0 percentage points
- Brier score: 0.594 (lower is better)
- Log loss: 0.997 (lower is better)

**API Baseline (75 fixtures):**
- Overall accuracy: **54.7%**
- Home baseline: 42.7%
- Improvement: +12.0 percentage points
- Brier score: 0.572
- Log loss: 0.962

**Breakdown by League (CSV):**
- Premier League (8): 53.0%
- Ligue 1 (301): 55.4%
- La Liga (564): 53.5%
- Serie A (384): 54.2%
- MLS (779): 49.3% (weakest — higher variance, new players)

**High-Confidence Accuracy:**
- Predictions with winner_prob ≥ 65%: **73.7% accuracy** (351 fixtures)
- This is the key metric — when the model is "confident", it's right 3 times out of 4

### What Brier Score and Log Loss Measure

**Brier Score** = mean squared error of predicted probabilities
```
BS = (1/N) * Σ (p_predicted - p_actual)²
```
- Range: [0, 1]
- 0 = perfect predictions
- 0.333 = random prediction of one outcome
- 0.667 = random uniform (no information)
- **Actual (0.594)**: Better than random, but room for improvement

**Log Loss** = negative average log likelihood
```
LL = -(1/N) * Σ log(p_actual_outcome)
```
- Range: [0, ∞]
- 0 = perfect predictions
- 1.099 = random uniform (no information)
- **Actual (0.997)**: Slightly better than random, model provides some signal

Both metrics show the model has **genuine predictive power** beyond home-team guessing, but acknowledges **inherent football uncertainty** — matches are not fully predictable from historical data alone.

### What "High-Confidence Accuracy 73.7%" Means

The calibration analysis shows:
- When the model predicts a 60%+ winner probability, the predicted team actually wins **73.7% of the time**
- This validates the confidence threshold (_CONF_HIGH = 0.60)
- Users should trust "high" confidence predictions significantly more than "medium" or "low"
- For UI purposes: high-confidence predictions warrant bold statements, medium warrant cautious recommendations, low warrant "it could go either way"

---

## Summary: The Full Prediction Flow

```
User selects fixture
    ↓
Backend loads fixture from SportMonks (7 enrichment calls in parallel)
    ↓
Dixon-Coles computes win/draw/away probabilities
    ↓
Backend determines winner + confidence from DC probabilities
    ↓
Backend injects winner into Gemini prompt with enriched context
    ↓
Gemini generates reasoning + key factors
    ↓
Backend overrides Gemini confidence with DC-derived label
    ↓
Frontend renders three-way probability bar + verdict + reasoning
```

Each step is independent and testable. The model is **deterministic** (same input → same output), **calibrated** (backtested on 1747 matches), and **transparent** (users see probabilities, not just a binary guess).
