# How the AI Sports Outcome Predictor Works

## Overview

The AI Sports Outcome Predictor combines statistical modeling (Dixon-Coles) with AI reasoning (Gemini) to predict football match outcomes. The pipeline flows from fixture selection through data enrichment, statistical analysis, winner determination, AI reasoning, and finally response assembly. Each step is independent but ordered, so the output of one feeds the next.

---

## STEP 1: Fixture Selection

### Where Fixtures Come From

Fixtures come from the **football-data.org v4 API** (https://www.football-data.org/documentation/quickstart) on its free tier, which allows 10 requests per minute. The app fetches the soonest upcoming (and very recent) fixtures for 6 competitions:
- Premier League (`PL`, id 2021)
- Bundesliga (`BL1`, id 2002)
- La Liga (`PD`, id 2014)
- Serie A (`SA`, id 2019)
- Ligue 1 (`FL1`, id 2015)
- Champions League (`CL`, id 2001)

The backend's `/api/fixtures` endpoint calls `get_upcoming_fixtures()` in `storage/league_data_client.py`, which asks each competition for its matches over a wide forward window (today−3 → today+180) and keeps the soonest non-finished fixtures per competition. The wide window matters in the European off-season: the next season's opening fixtures still appear instead of the page falling back to mocks.

Results are cached (5-minute TTL in the client, 5 minutes again in the backend) because of the 10 requests/minute free-tier limit. If the API key is missing or every competition errors, the app returns demo fixtures flagged with `_isMock: true` so the dashboard is never empty — those fixtures deliberately cannot be predicted, since there is no real data behind them.

### What Data Is in a Fixture Object

A normalized fixture contains:
- `id`: Unique fixture identifier (string)
- `name`: Human-readable match name (e.g., "Liverpool vs Manchester City")
- `homeTeam`: `{id, name, logo}` — home team object
- `awayTeam`: `{id, name, logo}` — away team object
- `startingAt`: ISO 8601 kickoff time (string)
- `leagueId`: football-data.org competition id (integer)
- `leagueName`: Human-readable league name (string)
- `seasonId`: football-data.org competition code (e.g. `PL`) used for standings/stats lookups
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

Before making a prediction, the backend enriches the fixture with 7 parallel football-data.org calls. They fetch recent form, current standings, squad depth and top scorers. All 7 run concurrently via `asyncio.gather()`, so the wall-clock cost is the slowest single call, not the sum. Every call is individually wrapped so a failure degrades that one field instead of failing the prediction.

### Which Calls Run (and When)

All 7 calls execute in parallel as soon as `/api/fixtures/{match_id}/prediction` is invoked (assuming the fixture is real, not mocked). The calls are:

**1. Recent Form: Team A**
```
GET /v4/teams/{team_a_id}/matches?status=FINISHED&dateFrom={start}&dateTo={end}
```
Returns team A's completed fixtures over the last 60 days, newest first, capped at 5. Parsed to extract opponent, kickoff date and result (Win/Draw/Loss).

**2. Recent Form: Team B**
Same endpoint as #1 for `team_b_id`.

**3. Season Standings**
```
GET /v4/competitions/{code}/standings
```
Returns the full table: position, points, W/D/L, goals scored, goals conceded, goal difference. The backend derives each team's season stats (`goals_scored`, `goals_conceded`, `total_matches`, `avg_goals_per_game`) directly from this response — zero extra API calls — and also returns the table to the frontend.

**4. xG and Trends**
Expected goals are **not on the free tier**. `get_fixture_with_xg()` returns a graceful empty payload (`xg: null`, `trends: null`), and the prompt simply omits that section.

**5. Confirmed Lineups**
Also **not on the free tier**. `get_fixture_lineups()` returns `{team_a_starters: [], team_b_starters: [], confirmed: false}`.

**6. Top Scorers**
```
GET /v4/competitions/{code}/scorers?limit=10
```
Returns the leading scorers in the competition — player name, team, goals — used by Gemini as squad context.

**7. Squad Depth**
```
GET /v4/teams/{team_a_id}
```
Returns team A's squad list (names, positions), used as depth context in the prompt.

Injuries follow the same pattern: not available on the free tier, so both teams report "Full squad available" rather than inventing absences.

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
  "injuries": {team_a: list[dict], team_b: list[dict]} — empty on the free tier,
  "lineup": {team_a_starters: list[dict], team_b_starters: list[dict], confirmed: bool},
  "topscorers_with_names": list[dict],
  "squad_a": list[dict],
  "season_id": str — football-data.org competition code
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
| MLS (historical backtest data only) | 779 | 1.08 | Weakest — large travel distances, less crowd effect |
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

if winner_prob >= _CONF_HIGH (0.65):
    confidence = "high"
elif winner_prob >= _CONF_MEDIUM (0.45):
    confidence = "medium"
else:
    confidence = "low"
```

These thresholds come from the backtest:
- **High-confidence predictions** (≥65% winner prob) hit **59.3% accuracy** on 344 fixtures in the point-in-time backtest, versus 48.4% overall
- So "high" means clearly favoured — roughly 3 right out of 5, not 3 out of 4
- Medium and low bins are closer to a coin flip between two of the three outcomes

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
Retrieved from `compare_matchup()`, which derives head-to-head history from each team's recent football-data.org fixtures.

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

The backtest evaluates the model on **historical fixtures with known outcomes**. `scripts/backtest.py` runs fully offline against the bundled dataset `scripts/data/enriched_fixtures.csv` (1,747 completed fixtures across 5 leagues) — no API key, no network, so the baseline is reproducible on any machine.

It has two modes:

1. **Point-in-time (default)** — each fixture is predicted using ONLY matches played before it, with the first 4 games per team skipped as warm-up. This is the honest number.
2. **Leaky (`--leaky`)** — reproduces the older run that used end-of-season aggregates for every fixture, including matches that had not been played yet. Kept only as a contrast, to show how much lookahead flatters a backtest.

### Current Accuracy Numbers

**Point-in-time baseline (1,526 fixtures evaluated, 220 skipped as warm-up):**
- Overall accuracy: **48.4%** (±2.5% at 95% CI)
- Home baseline (always predict home): 44.3%
- Improvement: +4.1 percentage points
- Brier score: 0.635 (lower is better)
- Log loss: 1.059 (lower is better)
- Top-label ECE: 0.073 | multiclass ECE: 0.050

**Leaky contrast (same code, full-season aggregates, 1,747 fixtures):**
- Overall accuracy: 52.8% | Brier 0.594 | Log loss 0.997
- The ~4.5pp gap between the two rows *is* the lookahead effect. Any accuracy figure quoted for this project should be the point-in-time one.

**Breakdown by league (point-in-time):**
- Premier League: 45.2%
- Ligue 1: 46.1%
- La Liga: 48.9%
- Serie A: 50.2%
- MLS (in the historical dataset only): 49.6%

**By outcome:** home wins 52.2% | draws 31.4% | away wins 43.0% — draws remain the hardest class, as expected from a Poisson-family model.

**High-confidence accuracy:**
- Predictions with winner probability ≥ 65%: **59.3%** on 344 fixtures.
- That is well above the 48.4% overall rate, so the confidence label carries real signal — but it is materially lower than the 73.7% the earlier lookahead-contaminated run reported.

### What Brier Score and Log Loss Measure

**Brier Score** = mean squared error of predicted probabilities
```
BS = (1/N) * Σ (p_predicted - p_actual)²
```
- Range: [0, 1]
- 0 = perfect predictions
- 0.333 = random prediction of one outcome
- 0.667 = random uniform (no information)
- **Actual (0.635, point-in-time)**: Better than uniform guessing, with clear room to improve

**Log Loss** = negative average log likelihood
```
LL = -(1/N) * Σ log(p_actual_outcome)
```
- Range: [0, ∞]
- 0 = perfect predictions
- 1.099 = random uniform (no information)
- **Actual (1.059, point-in-time)**: Close to uniform — the model's edge is real but modest

Both metrics show the model has **genuine predictive power** beyond home-team guessing, while acknowledging **inherent football uncertainty** — matches are not fully predictable from historical data alone.

### What the Confidence Label Means

The calibration analysis shows:
- When the model predicts a ≥65% winner probability, that team actually wins **59.3% of the time** (344 fixtures, point-in-time).
- The label is therefore informative but over-confident: a "high" prediction should be read as "clearly favoured", not "near-certain".
- For UI purposes: high-confidence predictions warrant a firm statement, medium a cautious one, low an explicit "this could go either way".

---

## Summary: The Full Prediction Flow

```
User selects fixture
    ↓
Backend loads fixture from football-data.org (7 enrichment calls in parallel)
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

Each step is independent and testable. The model is **deterministic** (same input → same output), **evaluated** (point-in-time backtest over 1,526 matches, no lookahead), and **transparent** (users see probabilities, not just a binary guess).
