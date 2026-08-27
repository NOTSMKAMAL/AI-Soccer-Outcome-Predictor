#!/usr/bin/env python3
"""
Backtesting and evaluation harness for the Dixon-Coles prediction engine.

Runs fully offline against the bundled historical dataset
(scripts/data/enriched_fixtures.csv) — no API key and no network needed, so the
baseline is reproducible on any machine.

Functional evaluation (CS180 Lab 4 / Lecture 10-11):
  Does the model's visible output match the requirement — predicted outcome
  aligns with actual match result?

Regression harness (CS180 Lecture 14):
  Re-run after any change to dixon_coles_probability() to confirm accuracy
  did not regress. Save scripts/backtest_results.json as the baseline record.

Architecture boundary (3-layer):
  storage → engine → interface
  This script sits below the interface layer and calls the engine directly.
  No FastAPI routes, no Gemini, no frontend code, zero API calls.

Run from project root with venv activated:
  python3 scripts/backtest.py            # point-in-time (no lookahead)
  python3 scripts/backtest.py --leaky    # old lookahead-contaminated contrast
"""

import argparse
import csv
import json
import math
import os
import sys
from datetime import date

# Add project root to sys.path so storage/engine imports resolve when the
# script is executed as  python3 scripts/backtest.py  from the project root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows consoles default to cp1252, which can't encode some report glyphs
# (arrows, Greek delta). Force UTF-8 so the report never crashes on output.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from engine.prediction_engine import dixon_coles_probability        # pure computation

# Shared calibration/scoring (P3). scripts/ is on sys.path when run as a script.
from calibration import (
    top_label_reliability, multiclass_ece, print_reliability, write_reliability_html,
    brier_and_logloss,
)


# ── Constants ──────────────────────────────────────────────────────────────────

# League ids as they appear in the historical backtest dataset.
LEAGUE_NAMES: dict[int, str] = {
    8:   "Premier League",
    301: "Ligue 1",
    564: "La Liga",
    384: "Serie A",
    779: "MLS",
}

BACKTEST_LEAGUE_IDS: set[int] = set(LEAGUE_NAMES)

# Prediction is labelled "high-confidence" when the winning probability
# returned by Dixon-Coles reaches this threshold.
CONFIDENCE_THRESHOLD = 0.65

# CSV mode constants
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "enriched_fixtures.csv")
MATCHES_PLAYED_PROXY = 34  # Fixed season-length proxy for CSV mode


# ── CSV helpers ────────────────────────────────────────────────────────────────

def _load_csv_fixtures() -> tuple[list[dict], int]:
    """Load fixtures from enriched_fixtures.csv and build fixture dicts for evaluation.

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


def _load_csv_fixtures_pit(min_prior: int = 4) -> tuple[list[dict], int]:
    """
    Point-in-time loader (P1 — zero lookahead).

    Walks every fixture in chronological order and builds each team's
    goals-scored / goals-conceded / matches-played and last-5 form from ONLY
    the matches that occurred *before* the fixture being predicted. This
    replaces the previous loader, which used one-shot full-season aggregates
    (an end-of-season snapshot used to "predict" earlier fixtures = lookahead).

    Fixtures where either team has fewer than `min_prior` prior in-season
    matches are skipped (cold-start warm-up), but still update the running
    state. Returns (fixtures, skipped_count).
    """
    from collections import deque

    raw_rows: list[dict] = []
    try:
        with open(CSV_PATH, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                print(f"ERROR: {CSV_PATH} has no header row")
                sys.exit(1)
            for row in reader:
                try:
                    outcome = row["actual_outcome"].strip()
                    if outcome not in ("home_win", "draw", "away_win"):
                        continue
                    raw_rows.append({
                        "fixture_id": int(row["fixture_id"]),
                        "league_id": int(row["league_id"]),
                        "season_id": int(row["season_id"]),
                        "date": (row["match_date"] or "")[:10],
                        "home_id": int(row["home_team_id"]),
                        "away_id": int(row["away_team_id"]),
                        "hg": int(row["home_goals"]),
                        "ag": int(row["away_goals"]),
                        "actual": outcome,
                    })
                except (ValueError, KeyError):
                    continue
    except FileNotFoundError:
        print(f"ERROR: {CSV_PATH} not found. Run: python3 scripts/pull_training_data.py")
        sys.exit(1)

    # Chronological order is what makes this zero-lookahead.
    raw_rows.sort(key=lambda r: (r["date"], r["fixture_id"]))

    # state[(season_id, team_id)] = running tallies from prior matches only.
    state: dict[tuple[int, int], dict] = {}

    def _st(season: int, team: int) -> dict:
        key = (season, team)
        if key not in state:
            state[key] = {"gs": 0.0, "ga": 0.0, "n": 0, "last5": deque(maxlen=5)}
        return state[key]

    fixtures: list[dict] = []
    skipped = 0
    for r in raw_rows:
        hs = _st(r["season_id"], r["home_id"])
        aw = _st(r["season_id"], r["away_id"])

        if hs["n"] >= min_prior and aw["n"] >= min_prior:
            rec = {
                "fixture_id": r["fixture_id"],
                "league_id": r["league_id"],
                "home_team_id": r["home_id"],
                "away_team_id": r["away_id"],
                "actual_outcome": r["actual"],
                "home_stats": {
                    "goals_scored": hs["gs"], "goals_conceded": hs["ga"],
                    "total_matches": float(hs["n"]),
                },
                "away_stats": {
                    "goals_scored": aw["gs"], "goals_conceded": aw["ga"],
                    "total_matches": float(aw["n"]),
                },
            }
            h5, a5 = list(hs["last5"]), list(aw["last5"])
            if len(h5) >= 3 and len(a5) >= 3:
                # Engine expects SUMS over the window plus rounds_used (it divides).
                rec["rolling_form"] = {
                    "home_scored_5r": float(sum(s for s, _ in h5)),
                    "home_conceded_5r": float(sum(c for _, c in h5)),
                    "away_scored_5r": float(sum(s for s, _ in a5)),
                    "away_conceded_5r": float(sum(c for _, c in a5)),
                    "home_rounds_used": len(h5),
                    "away_rounds_used": len(a5),
                }
            fixtures.append(rec)
        else:
            skipped += 1

        # Update AFTER reading — the just-played result must not inform itself.
        hs["gs"] += r["hg"]; hs["ga"] += r["ag"]; hs["n"] += 1; hs["last5"].append((r["hg"], r["ag"]))
        aw["gs"] += r["ag"]; aw["ga"] += r["hg"]; aw["n"] += 1; aw["last5"].append((r["ag"], r["hg"]))

    if not fixtures:
        print(f"ERROR: No fixtures left after point-in-time warm-up (min_prior={min_prior}).")
        sys.exit(1)
    return fixtures, skipped


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


def _eval_fixtures(fixtures: list[dict]) -> tuple[list[dict], dict, int]:
    """Run Dixon-Coles over a list of prepared fixtures and build metric records."""
    records: list[dict] = []
    data_source_counts: dict[str | None, int] = {}
    skipped_pred = 0
    for f in fixtures:
        predicted, confidence, probs, data_source = _predict(
            f.get("home_stats", {}), f.get("away_stats", {}),
            league_id=f.get("league_id"), rolling_form=f.get("rolling_form"),
        )
        if predicted is None:
            skipped_pred += 1
            continue
        actual = f.get("actual_outcome")
        data_source_counts[data_source] = data_source_counts.get(data_source, 0) + 1
        records.append({
            "fixture_id": f.get("fixture_id"), "league_id": f.get("league_id"),
            "actual": actual, "predicted": predicted, "confidence": confidence,
            "probs": probs, "correct": predicted == actual, "data_source": data_source,
        })
    return records, data_source_counts, skipped_pred


# ── Main ───────────────────────────────────────────────────────────────────────

def run_backtest_csv(leaky: bool = False) -> None:
    """Run backtest using CSV fixture data instead of API calls.

    Default is point-in-time (zero lookahead). Pass leaky=True to reproduce the
    previous (lookahead-contaminated) full-season-aggregate result for contrast.
    """
    today = date.today().isoformat()

    mode_tag = "LEAKY / full-season aggregates" if leaky else "POINT-IN-TIME / no lookahead"
    print(f"\n=== BACKTESTING HARNESS (CSV MODE — {mode_tag}) — starting {today} ===\n")

    # ── Step 1: Load fixtures from CSV ────────────────────────────────────────────
    print("Step 1: Loading fixtures from CSV...")
    if leaky:
        csv_fixtures, skipped = _load_csv_fixtures()
    else:
        csv_fixtures, skipped = _load_csv_fixtures_pit()
    print(f"  Loaded: {len(csv_fixtures)} fixtures | Skipped ({'bad data' if leaky else 'warm-up + bad data'}): {skipped}")
    print(f"  Data source: {CSV_PATH}")
    print()

    # ── Step 2: Run predictions (no API calls) ────────────────────────────────────
    print("Step 2: Running Dixon-Coles predictions (0 API calls — pure computation)...")
    records, data_source_counts, skipped_pred = _eval_fixtures(csv_fixtures)

    print(f"  Evaluated: {len(records)} fixtures | Skipped (prediction failed): {skipped_pred}")
    print()

    if not records:
        print("ERROR: 0 fixtures evaluated.")
        sys.exit(1)

    # Same-code leaky run, used only for an honest apples-to-apples contrast in
    # the report (isolates the lookahead effect from data/code drift).
    leaky_summary = None
    if not leaky:
        leaky_fx, _ = _load_csv_fixtures()
        leaky_records, _, _ = _eval_fixtures(leaky_fx)
        if leaky_records:
            lb, ll = brier_and_logloss(leaky_records)
            leaky_summary = {
                "acc": sum(1 for r in leaky_records if r["correct"]) / len(leaky_records),
                "brier": lb, "logloss": ll, "n": len(leaky_records),
            }

    # ── Step 3: Compute metrics (identical to API mode) ─────────────────────────
    _compute_and_report_metrics(records, today, mode="csv", csv_skipped=skipped, data_source_counts=data_source_counts, pit=not leaky, leaky_summary=leaky_summary)


def _compute_and_report_metrics(
    records: list[dict],
    today: str,
    mode: str = "api",
    csv_skipped: int = 0,
    data_source_counts: dict | None = None,
    pit: bool = False,
    leaky_summary: dict | None = None,
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

    # ── Calibration suite (P3): reliability diagram + ECE ───────────────────────
    reliability_bins, ece = top_label_reliability(records, n_bins=10)
    mc_ece = multiclass_ece(records, n_bins=10)
    reliability_html = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data",
        f"reliability_league_{'pit' if pit else 'leaky'}.html",
    )
    html_ok = write_reliability_html(
        reliability_bins, reliability_html,
        title=f"League engine ({'point-in-time' if pit else 'leaky'})", ece=ece,
    )

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

    if mode == "csv" and not pit:
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

    print("RELIABILITY DIAGRAM (P3 — predicted confidence vs observed accuracy):")
    print_reliability(reliability_bins, ece, title="  League engine")
    print(f"  Multiclass (one-vs-rest pooled) ECE: {mc_ece:.4f}")
    print("  [ECE = mean gap between confidence and reality; lower is better. "
          "Negative gap = overconfident.]")
    if html_ok:
        print(f"  Interactive diagram -> {reliability_html}")
    print()

    # Data source breakdown (CSV mode only)
    if mode == "csv" and data_source_counts:
        print("DATA SOURCE BREAKDOWN:")
        # Support 40/60, 30/70, and 20/80 blend variants
        rolling_blend_40_60 = data_source_counts.get("rolling_blend_40_60", 0)
        rolling_blend_30_70 = data_source_counts.get("rolling_blend_30_70", 0)
        rolling_blend_20_80 = data_source_counts.get("rolling_blend_20_80", 0)
        rolling_blend_count = rolling_blend_40_60 + rolling_blend_30_70 + rolling_blend_20_80
        season_stats_count = data_source_counts.get("season_stats", 0)
        standings_count = data_source_counts.get("standings", 0)
        total = rolling_blend_count + season_stats_count + standings_count

        # Determine which blend variant is being used
        blend_variant = "40/60" if rolling_blend_40_60 > 0 else "30/70" if rolling_blend_30_70 > 0 else "20/80" if rolling_blend_20_80 > 0 else "unknown"
        blend_form_weight = 0.40 if rolling_blend_40_60 > 0 else 0.30 if rolling_blend_30_70 > 0 else 0.20 if rolling_blend_20_80 > 0 else 0.0
        blend_season_weight = 1.0 - blend_form_weight

        if total > 0:
            print(f"  Weighted blend ({blend_variant}): {rolling_blend_count} fixtures ({100 * rolling_blend_count / total:.1f}% of total)")
            print(f"  Season statistics:     {season_stats_count} fixtures ({100 * season_stats_count / total:.1f}% of total)")
            print(f"  Standings fallback:    {standings_count} fixtures ({100 * standings_count / total:.1f}% of total)")
            print()

            # Calculate accuracy by data source
            blend_correct = sum(1 for r in records if r.get("data_source") in ("rolling_blend_40_60", "rolling_blend_30_70", "rolling_blend_20_80") and r["correct"])
            blend_total = rolling_blend_count
            season_stats_correct = sum(1 for r in records if r.get("data_source") == "season_stats" and r["correct"])
            season_stats_total = season_stats_count
            standings_correct = sum(1 for r in records if r.get("data_source") == "standings" and r["correct"])
            standings_total = standings_count

            print("WEIGHTED BLEND PARAMETERS:")
            print(f"  Recent form weight:    {int(blend_form_weight*100)}% (5-round rolling avg)")
            print(f"  Season history weight: {int(blend_season_weight*100)}% (full season avg)")
            print(f"  Blend formula: {blend_form_weight} × rolling_gpg + {blend_season_weight} × season_gpg")
            print(f"  Fixtures using blend:  {blend_total}")
            print(f"  Fixtures using standings: {standings_total}")
            print()

            print("COMPARISON vs ALL BASELINES:")
            if blend_total > 0:
                blend_acc = blend_correct / blend_total
                print(f"  Weighted blend ({blend_variant}): {blend_acc:.1%} accuracy ({blend_total} fixtures)")
            if standings_total > 0:
                standings_acc = standings_correct / standings_total
                print(f"  Pure standings:        {standings_acc:.1%} accuracy ({standings_total} fixtures)")
            if season_stats_total > 0:
                season_acc = season_stats_correct / season_stats_total
                print(f"  Season statistics:     {season_acc:.1%} accuracy ({season_stats_total} fixtures)")
            if blend_total > 0 and standings_total > 0:
                delta_acc = (blend_acc - standings_acc) * 100
                sign = "+" if delta_acc >= 0 else ""
                print(f"  Blend vs standings delta:    {sign}{delta_acc:.1f} pp")
            print()

    # Honest point-in-time vs leaky baseline (the whole point of P1).
    if mode == "csv" and pit:
        print("LOOKAHEAD EFFECT (the point of P1):")
        print(f"  {'':32}{'acc':>7} {'Brier':>8} {'LogLoss':>8} {'n':>6}")
        print(f"  Recorded snapshot (stale):      "
              f"{0.5335:>6.1%} {0.4734:>8.4f} {0.7835:>8.4f} {1747:>6}")
        if leaky_summary:
            print(f"  Same-code LEAKY (full-season):  "
                  f"{leaky_summary['acc']:>6.1%} {leaky_summary['brier']:>8.4f} "
                  f"{leaky_summary['logloss']:>8.4f} {leaky_summary['n']:>6}")
        print(f"  Same-code POINT-IN-TIME (honest):"
              f"{overall_acc:>6.1%} {brier_score:>8.4f} {log_loss:>8.4f} {n:>6}")
        if leaky_summary:
            print(f"  True lookahead effect:          "
                  f"{(overall_acc - leaky_summary['acc']) * 100:>+5.1f}pp "
                  f"{brier_score - leaky_summary['brier']:>+8.4f} "
                  f"{log_loss - leaky_summary['logloss']:>+8.4f}")
        print("  [Compare the two SAME-CODE rows for the real lookahead effect; the")
        print("   stale snapshot also differs due to data/code drift, not just leakage.]")
        print()

    if mode == "csv" and not pit:
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
        print(f"  Run: python3 scripts/backtest.py")
    else:
        print(f"  This run accuracy: {overall_acc:.1%} on {n} fixtures (±{margin:.1%} at 95% CI)")
        print(f"  Run: python3 scripts/backtest.py")
    print("  Re-run after model changes to detect regression.")
    print("  Per CS180 Lecture 13: regression testing provides confidence")
    print("  modifications did not adversely impact software quality.")
    print()

    print("KNOWN LIMITATIONS:")
    if mode == "csv" and pit:
        print("  - Point-in-time: each fixture uses ONLY prior in-season matches.")
        print(f"    First {4} games per team are skipped as warm-up (no lookahead).")
        print("  - Single season only (no cross-season carryover of ratings yet).")
    elif mode == "csv":
        print("  - matches_played derived from goals (2.7 avg/match) — may deviate")
        print("    from true match count if team scoring rate differs from league avg")
        print("  - Standings are end-of-season snapshots not match-day (LOOKAHEAD).")
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
        "point_in_time": pit,
        "reliability_ece": round(ece, 4),
        "multiclass_ece": round(mc_ece, 4),
        "reliability_bins": [
            {
                "lo": round(b["lo"], 2), "hi": round(b["hi"], 2), "count": b["count"],
                "mean_conf": _safe_acc(b["mean_conf"]), "accuracy": _safe_acc(b["accuracy"]),
            }
            for b in reliability_bins
        ],
        "limitations": [
            "end-of-season standings proxy — not match-day standings",
            "draws systematically underweighted by Poisson model",
            f"sample size {n} may be insufficient for statistical significance",
        ],
    }

    if mode == "csv":
        json_output["source_file"] = CSV_PATH
        json_output["skipped_fixtures"] = csv_skipped
        if pit:
            json_output["limitations"] = [
                "point-in-time: first 4 games/team skipped as warm-up",
                "single season only — no cross-season rating carryover yet",
                "draws systematically underweighted by Poisson model",
            ]
        else:
            json_output["limitations"].insert(0, "matches_played derived from goals (2.7 avg/match) — may deviate from true if team scoring rate differs from league avg")
        # Point-in-time (honest, no-lookahead) is now the canonical baseline that
        # the regression tests guard. The leaky run writes to a separate file and
        # exists only for explicit lookahead-effect comparison.
        results_name = "backtest_csv_results.json" if pit else "backtest_csv_results_leaky.json"
        out_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "data", results_name
        )
    else:
        out_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "backtest_results.json"
        )

    with open(out_path, "w") as fh:
        json.dump(json_output, fh, indent=2)
    print(f"\nResults saved -> {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Backtest Dixon-Coles prediction engine on fixture data"
    )
    parser.add_argument(
        "--leaky",
        action="store_true",
        help="Reproduce the old lookahead-contaminated full-season-aggregate result "
             "for contrast. Default is point-in-time (no lookahead).",
    )
    args = parser.parse_args()

    run_backtest_csv(leaky=args.leaky)
