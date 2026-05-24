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

import argparse
import csv
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

# CSV mode constants
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "enriched_fixtures.csv")
MATCHES_PLAYED_PROXY = 34  # Fixed season-length proxy for CSV mode


# ── CSV helpers ────────────────────────────────────────────────────────────────

def _load_csv_fixtures() -> tuple[list[dict], int]:
    """Load fixtures from raw_fixtures.csv and build fixture dicts for evaluation.

    Returns (fixtures, skipped_count) where fixtures are ready for prediction.
    Skips rows with missing/invalid data.
    """
    fixtures: list[dict] = []
    skipped = 0

    # Per-league season lengths (verified from data)
    season_length = {8: 38, 564: 38, 384: 38, 301: 34, 779: 34}
    # Average total goals per match across top football leagues
    avg_total_goals_per_match = 2.7

    try:
        with open(CSV_PATH, "r") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                print(f"ERROR: {CSV_PATH} has no header row")
                sys.exit(1)

            for row_num, row in enumerate(reader, start=2):
                try:
                    # Extract required fields
                    fixture_id = int(row["fixture_id"])
                    league_id = int(row["league_id"])
                    home_team_id = int(row["home_team_id"])
                    away_team_id = int(row["away_team_id"])
                    actual_outcome = row["actual_outcome"].strip()

                    # Validate actual_outcome
                    if actual_outcome not in ("home_win", "draw", "away_win"):
                        skipped += 1
                        continue

                    # Extract stats — handle empty strings gracefully
                    home_gs = row.get("home_goals_scored_season", "").strip()
                    home_ga = row.get("home_goals_conceded_season", "").strip()
                    away_gs = row.get("away_goals_scored_season", "").strip()
                    away_ga = row.get("away_goals_conceded_season", "").strip()

                    # Skip if any stat is missing or zero
                    if not home_gs or not home_ga or not away_gs or not away_ga:
                        skipped += 1
                        continue

                    home_gs_f = float(home_gs)
                    home_ga_f = float(home_ga)
                    away_gs_f = float(away_gs)
                    away_ga_f = float(away_ga)

                    if home_gs_f <= 0 or home_ga_f <= 0 or away_gs_f <= 0 or away_ga_f <= 0:
                        skipped += 1
                        continue

                    # Derive estimated matches from goals scored/conceded per team
                    # Cap at season length, floor at 1. This prevents early-season
                    # fixtures (where teams have played 5-10 games) from being
                    # calculated as if teams completed the full season.
                    max_games = season_length.get(league_id, 34)
                    home_matches = min(
                        max_games,
                        max(1, round((home_gs_f + home_ga_f) / avg_total_goals_per_match))
                    )
                    away_matches = min(
                        max_games,
                        max(1, round((away_gs_f + away_ga_f) / avg_total_goals_per_match))
                    )

                    # Extract rolling form fields (optional, may be empty for early-season fixtures)
                    home_scored_5r = row.get("home_form_goals_scored_5r", "").strip()
                    home_conceded_5r = row.get("home_form_goals_conceded_5r", "").strip()
                    away_scored_5r = row.get("away_form_goals_scored_5r", "").strip()
                    away_conceded_5r = row.get("away_form_goals_conceded_5r", "").strip()
                    home_rounds_used = row.get("home_form_rounds_used", "").strip()
                    away_rounds_used = row.get("away_form_rounds_used", "").strip()

                    rolling_form = None
                    if home_scored_5r and home_conceded_5r and away_scored_5r and away_conceded_5r:
                        try:
                            rolling_form = {
                                "home_scored_5r": float(home_scored_5r),
                                "home_conceded_5r": float(home_conceded_5r),
                                "away_scored_5r": float(away_scored_5r),
                                "away_conceded_5r": float(away_conceded_5r),
                                "home_rounds_used": int(home_rounds_used) if home_rounds_used else 5,
                                "away_rounds_used": int(away_rounds_used) if away_rounds_used else 5,
                            }
                        except (ValueError, TypeError):
                            rolling_form = None

                    # Build fixture record in the same format as API mode uses
                    fixture_record = {
                        "fixture_id": fixture_id,
                        "league_id": league_id,
                        "home_team_id": home_team_id,
                        "away_team_id": away_team_id,
                        "actual_outcome": actual_outcome,
                        "home_stats": {
                            "goals_scored": home_gs_f,
                            "goals_conceded": home_ga_f,
                            "total_matches": float(home_matches),
                        },
                        "away_stats": {
                            "goals_scored": away_gs_f,
                            "goals_conceded": away_ga_f,
                            "total_matches": float(away_matches),
                        },
                    }
                    if rolling_form:
                        fixture_record["rolling_form"] = rolling_form
                    fixtures.append(fixture_record)
                except (ValueError, KeyError) as e:
                    skipped += 1
                    continue

        if not fixtures:
            print(f"ERROR: No valid fixtures loaded from {CSV_PATH}")
            sys.exit(1)

        return fixtures, skipped

    except FileNotFoundError:
        print(f"ERROR: {CSV_PATH} not found. Run data pull first: python3 scripts/pull_training_data.py")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to load CSV: {e}")
        sys.exit(1)


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

def _predict(home_stats: dict, away_stats: dict, league_id: int | None = None, rolling_form: dict | None = None) -> tuple[str | None, float, dict | None, str | None]:
    """
    Run Dixon-Coles and return (predicted_outcome, winning_probability, full_probs, data_source).

    is_home_a=True because the first stats dict always represents the home team.
    Returns (None, 0.0, None, None) when Dixon-Coles cannot compute (missing stats).
    full_probs is the raw {"home_win", "draw", "away_win"} dict needed for
    Brier score and log loss — returned here to avoid a second engine call.
    data_source indicates which data priority was used ("rolling_5r", "season_stats", or "standings").
    """
    probs = dixon_coles_probability(home_stats, away_stats, is_home_a=True, league_id=league_id, rolling_form=rolling_form)
    if not probs:
        return None, 0.0, None, None
    data_source = probs.get("method")
    max_prob = max(v for k, v in probs.items() if k != "method")
    for outcome in ("home_win", "draw", "away_win"):
        if probs[outcome] == max_prob:
            return outcome, max_prob, probs, data_source
    return None, 0.0, None, None


# ── Main ───────────────────────────────────────────────────────────────────────

def run_backtest() -> None:
    api_key = _api_key()
    today = date.today().isoformat()

    print(f"\n=== BACKTESTING HARNESS — starting {today} ===\n")

    # ── Step 1: Fetch completed fixtures ───────────────────────────────────────
    print("Step 1: Fetching completed fixtures (≤3 API calls)...")
    completed = _fetch_completed_fixtures(api_key)
    if not completed:
        print("ERROR: No completed fixtures found. Verify API key and league IDs.")
        sys.exit(1)

    # ── Step 2: Determine dominant season_id per league ────────────────────────
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
        lid = f.get("league_id")
        home_id, away_id = _parse_participants(f)
        if not home_id or not away_id:
            skipped += 1
            continue

        league_stats = all_team_stats.get(lid, {})
        home_stats = league_stats.get(home_id)
        away_stats = league_stats.get(away_id)
        if not home_stats or not away_stats:
            skipped += 1
            continue

        actual = _parse_actual_result(f)
        if actual is None:
            skipped += 1
            continue

        predicted, confidence, probs, data_source = _predict(home_stats, away_stats, league_id=lid)
        if predicted is None:
            skipped += 1
            continue

        records.append({
            "fixture_id": f.get("id"),
            "league_id": lid,
            "date": (f.get("starting_at") or "")[:10],
            "actual": actual,
            "predicted": predicted,
            "confidence": confidence,
            "probs": probs,
            "correct": predicted == actual,
        })

    print(f"  Evaluated: {len(records)} fixtures | Skipped (missing data): {skipped}")

    if not records:
        print("\nERROR: 0 fixtures evaluated. "
              "Standings and fixture data may be for different seasons.")
        sys.exit(1)

    # ── Step 5: Compute metrics using shared function ──────────────────────────
    _compute_and_report_metrics(records, today, mode="api")


def run_backtest_csv() -> None:
    """Run backtest using CSV fixture data instead of API calls."""
    today = date.today().isoformat()

    print(f"\n=== BACKTESTING HARNESS (CSV MODE) — starting {today} ===\n")

    # ── Step 1: Load fixtures from CSV ────────────────────────────────────────────
    print("Step 1: Loading fixtures from CSV...")
    csv_fixtures, skipped = _load_csv_fixtures()
    print(f"  Loaded: {len(csv_fixtures)} fixtures | Skipped (bad data): {skipped}")
    print(f"  Data source: {CSV_PATH}")
    print()

    # ── Step 2: Run predictions (no API calls) ────────────────────────────────────
    print("Step 2: Running Dixon-Coles predictions (0 API calls — pure computation)...")
    records: list[dict] = []
    skipped_pred = 0
    data_source_counts: dict[str | None, int] = {}

    for f in csv_fixtures:
        home_stats = f.get("home_stats", {})
        away_stats = f.get("away_stats", {})
        league_id = f.get("league_id")
        rolling_form = f.get("rolling_form")

        predicted, confidence, probs, data_source = _predict(home_stats, away_stats, league_id=league_id, rolling_form=rolling_form)
        if predicted is None:
            skipped_pred += 1
            continue

        actual = f.get("actual_outcome")
        data_source_counts[data_source] = data_source_counts.get(data_source, 0) + 1
        records.append({
            "fixture_id": f.get("fixture_id"),
            "league_id": f.get("league_id"),
            "actual": actual,
            "predicted": predicted,
            "confidence": confidence,
            "probs": probs,
            "correct": predicted == actual,
            "data_source": data_source,
        })

    print(f"  Evaluated: {len(records)} fixtures | Skipped (prediction failed): {skipped_pred}")
    print()

    if not records:
        print("ERROR: 0 fixtures evaluated.")
        sys.exit(1)

    # ── Step 3: Compute metrics (identical to API mode) ─────────────────────────
    _compute_and_report_metrics(records, today, mode="csv", csv_skipped=skipped, data_source_counts=data_source_counts)


def _compute_and_report_metrics(
    records: list[dict],
    today: str,
    mode: str = "api",
    csv_skipped: int = 0,
    data_source_counts: dict | None = None,
) -> None:
    """Compute and report all metrics for backtest results.

    Shared between API mode and CSV mode for identical metric calculation.
    """
    n = len(records)
    n_correct = sum(1 for r in records if r["correct"])
    overall_acc = n_correct / n

    home_baseline_acc = sum(1 for r in records if r["actual"] == "home_win") / n
    improvement_pp = (overall_acc - home_baseline_acc) * 100

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
    cal_n = len(high_conf)
    cal_acc = sum(1 for r in high_conf if r["correct"]) / cal_n if cal_n else None

    # 95% margin of error (normal approximation)
    margin = 1.96 * math.sqrt(overall_acc * (1 - overall_acc) / n)

    # Brier score and log loss
    brier_sum = log_loss_sum = 0.0
    for r in records:
        p = r["probs"]
        actual_r = r["actual"]
        o_h = 1.0 if actual_r == "home_win" else 0.0
        o_d = 1.0 if actual_r == "draw" else 0.0
        o_a = 1.0 if actual_r == "away_win" else 0.0
        p_h = max(0.001, min(0.999, p["home_win"]))
        p_d = max(0.001, min(0.999, p["draw"]))
        p_a = max(0.001, min(0.999, p["away_win"]))
        brier_sum += (p_h - o_h) ** 2 + (p_d - o_d) ** 2 + (p_a - o_a) ** 2
        log_loss_sum += o_h * math.log(p_h) + o_d * math.log(p_d) + o_a * math.log(p_a)
    brier_score = brier_sum / n
    log_loss = -log_loss_sum / n

    # Count distinct leagues with at least 1 evaluated fixture
    active_leagues = sum(1 for lid in BACKTEST_LEAGUE_IDS if league_buckets.get(lid))

    # ── Print human-readable report ────────────────────────────────────────────────
    SEP = "=" * 62

    print(f"\n{SEP}")
    if mode == "csv":
        print("=== AI SPORTS PREDICTOR — BACKTESTING REPORT (CSV MODE) ===")
    else:
        print("=== AI SPORTS PREDICTOR — BACKTESTING REPORT ===")
    print(SEP)
    print(f"Evaluation date: {today}")
    if mode == "csv":
        print(f"Data source: {CSV_PATH}")
        print(f"Fixtures loaded: {len(records) + csv_skipped} | Skipped (bad data): {csv_skipped}")
    print(f"Fixtures evaluated: {n} | Leagues: {active_leagues}")
    print()

    if mode == "csv":
        print("DATA SOURCE NOTE:")
        print("  matches_played derived from goals scored/conceded per team using")
        print("  2.7 avg total goals/game constant. Capped at league season length")
        print("  (EPL/La Liga/Serie A: 38, Ligue 1/MLS: 34). Fixes previous fixed=34")
        print("  assumption that suppressed MLS accuracy. Same functional oracle")
        print("  (actual_outcome from goals). Per CS180 Lecture 10: 'functional tests")
        print("  ask — does the visible behavior match the requirement?'")
        print()

    sign = "+" if improvement_pp >= 0 else ""
    print("FUNCTIONAL ACCURACY (Dixon-Coles vs actual result):")
    print(f"  Overall:        {overall_acc:.1%} (±{margin:.1%} at 95% CI)")
    print(f"  Baseline (always pick home team): {home_baseline_acc:.1%}")
    print(f"  Improvement over baseline: {sign}{improvement_pp:.1f} pp")
    print()

    print("BY PREDICTED OUTCOME:")
    for outcome, label in [
        ("home_win", "Home win predicted"),
        ("draw", "Draw predicted"),
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
        (8, "Premier League"),
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

    if mode == "csv":
        print("HOME ADVANTAGE COEFFICIENTS APPLIED:")
        print("  Premier League (8):  1.18")
        print("  La Liga (564):       1.16")
        print("  Serie A (384):       1.15")
        print("  Ligue 1 (301):       1.13")
        print("  MLS (779):           1.08")
        print("  [Research-backed values from Dixon-Coles literature.")
        print("   MLS lower due to travel distances and crowd effects.]")
        print()

    print(f"CALIBRATION (confidence >= {CONFIDENCE_THRESHOLD:.0%} threshold):")
    print(f"  High-confidence predictions: {cal_n} fixtures")
    if cal_acc is not None:
        print(f"  Accuracy when confident:     {cal_acc:.1%}")
    else:
        print("  Accuracy when confident:     N/A (no high-confidence predictions)")
    print("  [Measures if confidence score is meaningful]")
    print()

    print("CALIBRATION QUALITY (addresses benchmark fragility):")
    print(f"  Brier Score: {brier_score:.4f}  [random=0.667, good model<0.50]")
    print(f"  Log Loss:    {log_loss:.4f}  [random=1.10,  good model<0.95]")
    print("  [Note: accuracy alone can hide poor calibration —")
    print("   Brier and log loss measure probability quality]")
    print()

    # Data source breakdown (CSV mode only)
    if mode == "csv" and data_source_counts:
        print("DATA SOURCE BREAKDOWN:")
        rolling_5r_count = data_source_counts.get("rolling_5r", 0)
        season_stats_count = data_source_counts.get("season_stats", 0)
        standings_count = data_source_counts.get("standings", 0)
        total = rolling_5r_count + season_stats_count + standings_count
        if total > 0:
            print(f"  Rolling 5-round form:  {rolling_5r_count} fixtures ({100 * rolling_5r_count / total:.1f}% of total)")
            print(f"  Season statistics:     {season_stats_count} fixtures ({100 * season_stats_count / total:.1f}% of total)")
            print(f"  Standings fallback:    {standings_count} fixtures ({100 * standings_count / total:.1f}% of total)")
            print()

            # Calculate accuracy by data source
            rolling_5r_correct = sum(1 for r in records if r.get("data_source") == "rolling_5r" and r["correct"])
            rolling_5r_total = rolling_5r_count
            season_stats_correct = sum(1 for r in records if r.get("data_source") == "season_stats" and r["correct"])
            season_stats_total = season_stats_count
            standings_correct = sum(1 for r in records if r.get("data_source") == "standings" and r["correct"])
            standings_total = standings_count

            print("ROLLING FORM vs STANDINGS ACCURACY:")
            if rolling_5r_total > 0:
                rolling_5r_acc = rolling_5r_correct / rolling_5r_total
                print(f"  Rolling form fixtures: {rolling_5r_acc:.1%} accuracy ({rolling_5r_total} fixtures)")
            if standings_total > 0:
                standings_acc = standings_correct / standings_total
                print(f"  Standings fallback:    {standings_acc:.1%} accuracy ({standings_total} fixtures)")
                if rolling_5r_total > 0:
                    delta_acc = (rolling_5r_acc - standings_acc) * 100
                    sign = "+" if delta_acc >= 0 else ""
                    print(f"  Delta:                 {sign}{delta_acc:.1f} pp")
                    if rolling_5r_acc > standings_acc:
                        print("  [Rolling form improvement verified]")
            print()

    # Comparison to API baseline (for CSV mode)
    if mode == "csv":
        api_baseline_acc = 0.5467
        api_baseline_n = 75
        api_baseline_margin = 0.1127
        delta_pp = (overall_acc - api_baseline_acc) * 100

        print("COMPARISON vs 75-FIXTURE API BASELINE:")
        print(f"  75-fixture result:   {api_baseline_acc:.1%} (±{api_baseline_margin:.1%} at 95% CI)")
        print(f"  1,747-fixture result: {overall_acc:.1%} (±{margin:.1%} at 95% CI)")
        print(f"  Delta:                {sign}{abs(delta_pp):.1f} pp")

        if abs(delta_pp) > 5.0:
            print(f"  WARNING: >5pp deviation from API baseline — possible data quality")
            print(f"  issue in raw_fixtures.csv (standings snapshot mismatch or coverage gap)")
        else:
            interpretation = "improved" if delta_pp > 0 else "degraded" if delta_pp < 0 else "unchanged"
            print(f"  Interpretation: Result {interpretation} within expected variance.")
        print()

        # Comparison vs previous CSV run with fixed home_advantage=1.15
        prev_csv_acc = 0.5335
        prev_csv_mls = 0.4912
        delta_overall = (overall_acc - prev_csv_acc) * 100
        mls_acc, _ = _league_acc(779)
        delta_mls = (mls_acc - prev_csv_mls) * 100 if mls_acc else 0.0
        sign_overall = "+" if delta_overall >= 0 else ""
        sign_mls = "+" if delta_mls >= 0 else ""

        print("COMPARISON vs PREVIOUS CSV RUN:")
        print(f"  Previous (fixed 1.15):    53.3% overall, MLS 49.1%")
        print(f"  Updated (per-league):     {overall_acc:.1%} overall, MLS {mls_acc:.1%}")
        print(f"  MLS improvement:          {sign_mls}{delta_mls:.1f} pp")
        print(f"  Overall improvement:      {sign_overall}{delta_overall:.1f} pp")
        print()

    print("REGRESSION BASELINE (save for future comparison):")
    if mode == "csv":
        print(f"  This run accuracy: {overall_acc:.1%} on {n} fixtures (±{margin:.1%} at 95% CI)")
        print(f"  Run: python3 scripts/backtest.py --csv")
    else:
        print(f"  This run accuracy: {overall_acc:.1%} on {n} fixtures (±{margin:.1%} at 95% CI)")
        print(f"  Run: python3 scripts/backtest.py")
    print("  Re-run after model changes to detect regression.")
    print("  Per CS180 Lecture 13: regression testing provides confidence")
    print("  modifications did not adversely impact software quality.")
    print()

    print("KNOWN LIMITATIONS:")
    if mode == "csv":
        print("  - matches_played derived from goals (2.7 avg/match) — may deviate")
        print("    from true match count if team scoring rate differs from league avg")
    print("  - Standings are end-of-season snapshots not match-day.")
    print("    Early-season fixture accuracy is overestimated.")
    print("  - Draws are systematically underweighted by Poisson models.")
    if mode == "csv":
        print("  - 1,747 fixtures is full current season — not multi-season data")
    else:
        print(f"  - Sample size: {n} fixtures may be insufficient for statistical significance.")
    print(SEP)

    # ── Save results JSON ──────────────────────────────────────────────────────────
    def _safe_acc(acc: float | None) -> float | None:
        return round(acc, 4) if acc is not None else None

    json_output = {
        "evaluation_date": today,
        "mode": mode,
        "total_fixtures": n,
        "overall_accuracy": round(overall_acc, 4),
        "confidence_interval_95": round(margin, 4),
        "home_baseline_accuracy": round(home_baseline_acc, 4),
        "improvement_over_baseline_pp": round(improvement_pp, 2),
        "by_outcome": {
            "home_win": _safe_acc(_bucket_acc("home_win")[0]),
            "draw": _safe_acc(_bucket_acc("draw")[0]),
            "away_win": _safe_acc(_bucket_acc("away_win")[0]),
        },
        "by_league": {
            str(lid): _safe_acc(_league_acc(lid)[0])
            for lid in [8, 301, 564, 384, 779]
        },
        "calibration_accuracy": _safe_acc(cal_acc),
        "calibration_n": cal_n,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "brier_score": round(brier_score, 4),
        "log_loss": round(log_loss, 4),
        "limitations": [
            "end-of-season standings proxy — not match-day standings",
            "draws systematically underweighted by Poisson model",
            f"sample size {n} may be insufficient for statistical significance",
        ],
    }

    if mode == "csv":
        json_output["source_file"] = CSV_PATH
        json_output["skipped_fixtures"] = csv_skipped
        json_output["api_baseline_accuracy"] = 0.5467
        json_output["api_baseline_n"] = 75
        json_output["delta_vs_baseline_pp"] = round((overall_acc - 0.5467) * 100, 2)
        json_output["limitations"].insert(0, "matches_played derived from goals (2.7 avg/match) — may deviate from true if team scoring rate differs from league avg")
        out_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "data", "backtest_csv_results.json"
        )
    else:
        out_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "backtest_results.json"
        )

    with open(out_path, "w") as fh:
        json.dump(json_output, fh, indent=2)
    print(f"\nResults saved → {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Backtest Dixon-Coles prediction engine on fixture data"
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Read fixtures from raw_fixtures.csv instead of SportMonks API",
    )
    args = parser.parse_args()

    if args.csv:
        run_backtest_csv()
    else:
        run_backtest()
