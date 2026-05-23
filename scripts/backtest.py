#!/usr/bin/env python3
"""
Backtesting and evaluation harness for the Dixon-Coles prediction engine.

Functional evaluation (CS180 Lab 4 / Lecture 10-11):
  Does the model's visible output match the requirement — predicted outcome
  aligns with actual match result?

Regression harness (CS180 Lecture 14):
  Re-run after any change to dixon_coles_probability() to confirm accuracy
  did not regress. Save scripts/backtest_results.json as the baseline record.

Architecture boundary (3-layer per Lab 4 worksheet):
  storage → engine → interface
  This script sits below the interface layer and calls storage + engine
  directly. No FastAPI routes, no Gemini, no frontend code.

API budget: <= 50 SportMonks API calls per run.
  Actual: up to 3 (fixture pages) + 5 (standings) = 8 calls max. start

Run from project root with venv activated:
  python3 scripts/backtest.py
"""

import json
import math
import os
import sys
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

# Add project root to sys.path so storage/engine imports resolve when the
# script is executed as  python3 scripts/backtest.py  from the project root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from storage.sportmonks_client import get_season_standings          # 1 API call each
from engine.prediction_engine import dixon_coles_probability        # pure computation


# ── Constants ──────────────────────────────────────────────────────────────────

BASE_URL = "https://api.sportmonks.com/v3/football"

# 5 leagues confirmed on subscription (Bundesliga excluded per task spec)
BACKTEST_LEAGUE_IDS: set[int] = {8, 301, 564, 384, 779}

LEAGUE_NAMES: dict[int, str] = {
    8:   "Premier League",
    301: "Ligue 1",
    564: "La Liga",
    384: "Serie A",
    779: "MLS",
}

# Prediction is labelled "high-confidence" when the winning probability
# returned by Dixon-Coles reaches this threshold.
CONFIDENCE_THRESHOLD = 0.65

# Fetch fixtures this many days back from yesterday.  180 days ≈ half-season
# for European leagues; covers most of the MLS regular season as well.
# Increasing this window captures more fixtures but uses more API pages.
LOOKBACK_DAYS = 80


# ── API helpers ─────────────────────────────────────────────────────────────────

def _api_key() -> str:
    key = os.getenv("SPORTMONKS_API_KEY") or ""
    if not key:
        print("ERROR: SPORTMONKS_API_KEY is not set — add it to .env and retry.")
        sys.exit(1)
    return key


def _fetch_completed_fixtures(api_key: str) -> list[dict]:
    """
    Fetch completed fixtures for all 5 target leagues over the lookback window.

    Uses  GET /fixtures/between/{start}/{end}  with  include=scores;participants.
    Paginates up to 3 pages (100 fixtures each) to stay within the API budget.
    After fetching, filters to the 5 target leagues and fixtures that have a
    result (result_info field present and non-empty).

    API calls: 1–3
    """
    end   = date.today() - timedelta(days=1)
    start = end - timedelta(days=LOOKBACK_DAYS)
    url   = f"{BASE_URL}/fixtures/between/{start}/{end}"

    print(f"  Date range: {start} → {end}")

    all_raw: list[dict] = []
    for page in range(1, 4):           # hard cap at 3 pages = 3 API calls
        params: dict = {
            "api_token": api_key,
            "include":   "scores;participants",
            "per_page":  100,
            "page":      page,
        }
        try:
            resp = requests.get(url, params=params, timeout=30)
            if not resp.ok:
                print(f"  Page {page}: HTTP {resp.status_code} — stopping pagination")
                break
            data = resp.json().get("data", [])
            if not data:
                break
            all_raw.extend(data)
            print(f"  Page {page}: received {len(data)} fixtures")
            if len(data) < 25:
                break                  # reached the last page (API caps at 25 per page)
        except Exception as exc:
            print(f"  Page {page} request failed: {exc}")
            break

    completed = [
        f for f in all_raw
        if f.get("league_id") in BACKTEST_LEAGUE_IDS and f.get("result_info")
    ]
    print(f"  Total raw: {len(all_raw)}, in target leagues with result: {len(completed)}")
    return completed


# ── Parsing helpers ────────────────────────────────────────────────────────────

def _parse_actual_result(fixture: dict) -> str | None:
    """
    Determine actual match outcome from the scores include.

    Looks for score entries with description == "2ND_HALF" (SportMonks full-time
    score label — confirmed from live API; "CURRENT" does not exist).  Each
    2ND_HALF entry covers one side: participant="home" or participant="away".

    Functional oracle: the ground truth is the real scoreline — not inferred
    from any model output.

    Returns: 'home_win' | 'draw' | 'away_win' | None (if scores unavailable)
    """
    home_g: int | None = None
    away_g: int | None = None

    for entry in (fixture.get("scores") or []):
        if entry.get("description") != "2ND_HALF":
            continue
        score_obj = entry.get("score") or {}
        goals      = score_obj.get("goals")
        participant = score_obj.get("participant", "").lower()
        if goals is not None:
            if participant == "home":
                home_g = goals
            elif participant == "away":
                away_g = goals

    if home_g is None or away_g is None:
        return None
    if home_g > away_g:
        return "home_win"
    if home_g == away_g:
        return "draw"
    return "away_win"


def _parse_participants(fixture: dict) -> tuple[int | None, int | None]:
    """Return (home_team_id, away_team_id) from the participants include."""
    participants = fixture.get("participants") or []
    home_id = away_id = None
    for p in participants:
        loc = (p.get("meta") or {}).get("location", "")
        if loc == "home":
            home_id = p.get("id")
        elif loc == "away":
            away_id = p.get("id")
    return home_id, away_id


# ── Standings → team stats ─────────────────────────────────────────────────────

def _build_team_stats(season_id: int) -> dict[int, dict]:
    """
    Fetch season standings and return team_id → stats dict compatible with
    dixon_coles_probability() input format.

    Keys produced:
      goals_scored  — mapped directly from standings
      goals_against — dixon_coles checks "goals_against" as the second key
                      for goals_conceded (first key "goals_conceded" absent)
      total_matches — dixon_coles checks "total_matches" first for games played

    API calls: 1 (via get_season_standings)
    """
    result = get_season_standings(season_id)
    if result["status"] != "success":
        print(f"    standings error: {result.get('message', 'unknown')}")
        return {}

    stats: dict[int, dict] = {}
    for row in result.get("data", []):
        tid = row.get("participant_id")
        gs  = row.get("goals_scored")
        ga  = row.get("goals_against")
        tp  = row.get("total_played")
        if tid and gs is not None and ga is not None and tp and tp > 0:
            stats[tid] = {
                "goals_scored":  gs,
                "goals_against": ga,
                "total_matches": tp,
            }
    return stats


# ── Prediction ─────────────────────────────────────────────────────────────────

def _predict(home_stats: dict, away_stats: dict) -> tuple[str | None, float]:
    """
    Run Dixon-Coles and return (predicted_outcome, winning_probability).

    is_home_a=True because the first stats dict always represents the home team.
    Returns (None, 0.0) when Dixon-Coles cannot compute (missing stats).
    """
    probs = dixon_coles_probability(home_stats, away_stats, is_home_a=True)
    if not probs:
        return None, 0.0
    max_prob = max(probs.values())
    for outcome in ("home_win", "draw", "away_win"):
        if probs[outcome] == max_prob:
            return outcome, max_prob
    return None, 0.0


# ── Main ───────────────────────────────────────────────────────────────────────

def run_backtest() -> None:
    api_key = _api_key()
    today   = date.today().isoformat()

    print(f"\n=== BACKTESTING HARNESS — starting {today} ===\n")

    # ── Step 1: Fetch completed fixtures ───────────────────────────────────────
    print("Step 1: Fetching completed fixtures (≤3 API calls)...")
    completed = _fetch_completed_fixtures(api_key)
    if not completed:
        print("ERROR: No completed fixtures found. Verify API key and league IDs.")
        sys.exit(1)

    # ── Step 2: Determine dominant season_id per league ────────────────────────
    # Fixtures carry a season_id field.  Use the most-seen season_id per league
    # so that standings match the majority of the fixtures we test against.
    print("\nStep 2: Identifying season IDs from fixture data...")
    season_votes: dict[int, dict[int, int]] = {}
    for f in completed:
        lid = f.get("league_id")
        sid = f.get("season_id")
        if lid and sid:
            season_votes.setdefault(lid, {})
            season_votes[lid][sid] = season_votes[lid].get(sid, 0) + 1

    league_season_ids: dict[int, int] = {}
    for lid, votes in season_votes.items():
        best = max(votes, key=lambda k: votes[k])
        league_season_ids[lid] = best
        name = LEAGUE_NAMES.get(lid, str(lid))
        print(f"  {name}: season_id={best} ({votes[best]} fixtures)")

    # ── Step 3: Fetch standings per league (1 API call each = 5 calls) ─────────
    print("\nStep 3: Fetching standings per league (5 API calls)...")
    all_team_stats: dict[int, dict[int, dict]] = {}
    for lid, sid in league_season_ids.items():
        name = LEAGUE_NAMES.get(lid, str(lid))
        print(f"  {name} (season {sid})...")
        stats = _build_team_stats(sid)
        all_team_stats[lid] = stats
        print(f"    {len(stats)} teams with stats")

    # ── Step 4: Evaluate Dixon-Coles against each completed fixture ─────────────
    print("\nStep 4: Running Dixon-Coles predictions (0 API calls — pure computation)...")
    records: list[dict] = []
    skipped = 0

    for f in completed:
        lid      = f.get("league_id")
        home_id, away_id = _parse_participants(f)
        if not home_id or not away_id:
            skipped += 1
            continue

        league_stats = all_team_stats.get(lid, {})
        home_stats   = league_stats.get(home_id)
        away_stats   = league_stats.get(away_id)
        if not home_stats or not away_stats:
            skipped += 1
            continue

        actual = _parse_actual_result(f)
        if actual is None:
            skipped += 1
            continue

        predicted, confidence = _predict(home_stats, away_stats)
        if predicted is None:
            skipped += 1
            continue

        records.append({
            "fixture_id": f.get("id"),
            "league_id":  lid,
            "date":       (f.get("starting_at") or "")[:10],
            "actual":     actual,
            "predicted":  predicted,
            "confidence": confidence,
            "correct":    predicted == actual,
        })

    print(f"  Evaluated: {len(records)} fixtures | Skipped (missing data): {skipped}")

    if not records:
        print("\nERROR: 0 fixtures evaluated. "
              "Standings and fixture data may be for different seasons.")
        sys.exit(1)

    # ── Step 5: Compute metrics ────────────────────────────────────────────────
    n           = len(records)
    n_correct   = sum(1 for r in records if r["correct"])
    overall_acc = n_correct / n

    home_baseline_acc = sum(1 for r in records if r["actual"] == "home_win") / n
    improvement_pp    = (overall_acc - home_baseline_acc) * 100

    # By predicted outcome
    outcome_buckets: dict[str, list[bool]] = {
        "home_win": [], "draw": [], "away_win": []
    }
    for r in records:
        outcome_buckets[r["predicted"]].append(r["correct"])

    def _bucket_acc(key: str) -> tuple[float | None, int]:
        vals = outcome_buckets[key]
        if not vals:
            return None, 0
        return sum(vals) / len(vals), len(vals)

    # By league
    league_buckets: dict[int, list[bool]] = {lid: [] for lid in BACKTEST_LEAGUE_IDS}
    for r in records:
        league_buckets.setdefault(r["league_id"], []).append(r["correct"])

    def _league_acc(lid: int) -> tuple[float | None, int]:
        vals = league_buckets.get(lid, [])
        if not vals:
            return None, 0
        return sum(vals) / len(vals), len(vals)

    # Calibration: accuracy when model's max probability >= threshold
    high_conf = [r for r in records if r["confidence"] >= CONFIDENCE_THRESHOLD]
    cal_n     = len(high_conf)
    cal_acc   = sum(1 for r in high_conf if r["correct"]) / cal_n if cal_n else None

    # 95% margin of error (normal approximation)
    margin = 1.96 * math.sqrt(overall_acc * (1 - overall_acc) / n)

    # Count distinct leagues with at least 1 evaluated fixture
    active_leagues = sum(1 for lid in BACKTEST_LEAGUE_IDS if league_buckets.get(lid))

    # ── Step 6: Print human-readable report ────────────────────────────────────
    SEP = "=" * 62

    print(f"\n{SEP}")
    print("=== AI SPORTS PREDICTOR — BACKTESTING REPORT ===")
    print(SEP)
    print(f"Evaluation date: {today}")
    print(f"Fixtures evaluated: {n} | Leagues: {active_leagues}")
    print()

    sign = "+" if improvement_pp >= 0 else ""
    print("FUNCTIONAL ACCURACY (Dixon-Coles vs actual result):")
    print(f"  Overall:        {overall_acc:.1%}")
    print(f"  Baseline (always pick home team): {home_baseline_acc:.1%}")
    print(f"  Improvement over baseline: {sign}{improvement_pp:.1f} pp")
    print()

    print("BY PREDICTED OUTCOME:")
    for outcome, label in [
        ("home_win", "Home win predicted"),
        ("draw",     "Draw predicted"),
        ("away_win", "Away win predicted"),
    ]:
        acc, tot = _bucket_acc(outcome)
        if acc is not None:
            print(f"  {label:<26}{acc:.1%} correct ({tot} fixtures)")
        else:
            print(f"  {label:<26}N/A (no predictions)")
    print("  [Note: draws are hardest to predict — expected ~30%]")
    print()

    print("BY LEAGUE:")
    for lid, name in [
        (8,   "Premier League"),
        (301, "Ligue 1"),
        (564, "La Liga"),
        (384, "Serie A"),
        (779, "MLS"),
    ]:
        acc, tot = _league_acc(lid)
        tag = f"{name} ({lid}):"
        if acc is not None:
            print(f"  {tag:<22} {acc:.1%} ({tot} fixtures)")
        else:
            print(f"  {tag:<22} no fixtures evaluated")
    print()

    print(f"CALIBRATION (confidence >= {CONFIDENCE_THRESHOLD:.0%} threshold):")
    print(f"  High-confidence predictions: {cal_n} fixtures")
    if cal_acc is not None:
        print(f"  Accuracy when confident:     {cal_acc:.1%}")
    else:
        print("  Accuracy when confident:     N/A (no high-confidence predictions)")
    print("  [Measures if confidence score is meaningful]")
    print()

    print("REGRESSION BASELINE (save for future comparison):")
    print(f"  This run accuracy: {overall_acc:.1%} on {n} fixtures (±{margin:.1%} at 95% CI)")
    print("  Run this script again after model changes to detect")
    print("  regression per CS180 Lecture 14 regression testing.")
    print()

    print("KNOWN LIMITATIONS:")
    print("  - Standings are end-of-season snapshots not match-day.")
    print("    Early-season fixture accuracy is overestimated.")
    print("  - Draws are systematically underweighted by Poisson models.")
    print(f"  - Sample size: {n} fixtures may be insufficient for")
    print("    statistical significance. Report accuracy ± margin.")
    print(SEP)

    # ── Step 7: Save backtest_results.json ─────────────────────────────────────
    def _safe_acc(acc: float | None) -> float | None:
        return round(acc, 4) if acc is not None else None

    json_output = {
        "evaluation_date":        today,
        "total_fixtures":         n,
        "overall_accuracy":       round(overall_acc, 4),
        "home_baseline_accuracy": round(home_baseline_acc, 4),
        "improvement_over_baseline_pp": round(improvement_pp, 2),
        "margin_of_error_95pct":  round(margin, 4),
        "by_outcome": {
            "home_win": _safe_acc(_bucket_acc("home_win")[0]),
            "draw":     _safe_acc(_bucket_acc("draw")[0]),
            "away_win": _safe_acc(_bucket_acc("away_win")[0]),
        },
        "by_league": {
            str(lid): _safe_acc(_league_acc(lid)[0])
            for lid in [8, 301, 564, 384, 779]
        },
        "calibration_accuracy":   _safe_acc(cal_acc),
        "calibration_n":          cal_n,
        "confidence_threshold":   CONFIDENCE_THRESHOLD,
        "limitations": [
            "end-of-season standings proxy — not match-day standings",
            "draws systematically underweighted by Poisson model",
            f"sample size {n} may be insufficient for statistical significance",
        ],
    }

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_results.json")
    with open(out_path, "w") as fh:
        json.dump(json_output, fh, indent=2)
    print(f"\nResults saved → {out_path}")


if __name__ == "__main__":
    run_backtest()
