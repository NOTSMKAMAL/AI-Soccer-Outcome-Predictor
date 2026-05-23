#!/usr/bin/env python3
"""
Historical fixture data pull for Vertex AutoML training.

Architecture layer: storage (reads from SportMonks via storage/sportmonks_client.py).
Does NOT call: engine/prediction_engine.py, backend/main.py, any FastAPI endpoint, Gemini.

Per CS 180 Lecture 9 agentic design: preserves state across interruptions via checkpoint.
Per CS 180 Lecture 10: actual_outcome is a functional oracle derived from ground truth goals,
never inferred from a model.

Run from project root with venv activated:
  python3 scripts/pull_training_data.py
"""

import csv
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from storage.sportmonks_client import get_season_standings  # 1 API call each


# ── Constants ──────────────────────────────────────────────────────────────────

BASE_URL = "https://api.sportmonks.com/v3/football"
DAILY_CALL_BUDGET = 1500  # hard cap — 500 buffer from 2000/day limit

# Season IDs hardcoded from backtest run — 0 discovery calls needed
KNOWN_SEASONS: dict[int, dict] = {
    8:   {"season_id": 25583, "name": "Premier League"},
    564: {"season_id": 25659, "name": "La Liga"},
    384: {"season_id": 25533, "name": "Serie A"},
    301: {"season_id": 25651, "name": "Ligue 1"},
    779: {"season_id": 26720, "name": "MLS"},
}

DATA_DIR        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CSV_PATH        = os.path.join(DATA_DIR, "raw_fixtures.csv")
CHECKPOINT_PATH = os.path.join(DATA_DIR, "pull_checkpoint.json")

SEASON_DATE_FROM = "2025-07-01"   # covers MLS early season start
SEASON_DATE_TO   = "2026-05-23"   # current season end (today)

CSV_COLUMNS = [
    "fixture_id", "league_id", "season_id", "match_date",
    "home_team_id", "away_team_id",
    "home_goals", "away_goals",
    "actual_outcome",
    "home_standing_pos", "away_standing_pos",
    "home_goals_scored_season", "home_goals_conceded_season",
    "away_goals_scored_season", "away_goals_conceded_season",
    "home_form_last5",
    "h2h_home_wins", "h2h_away_wins", "h2h_draws",
]


# ── API helpers ────────────────────────────────────────────────────────────────

def _api_key() -> str:
    key = os.getenv("SPORTMONKS_API_KEY") or ""
    if not key:
        print("ERROR: SPORTMONKS_API_KEY is not set — add it to .env and retry.")
        sys.exit(1)
    return key


def _get(url: str, params: dict, call_count: list) -> dict | None:
    """Make one GET request, increment call_count[0], return parsed JSON or None on error."""
    call_count[0] += 1
    try:
        resp = requests.get(url, params=params, timeout=30)
        if not resp.ok:
            print(f"    HTTP {resp.status_code} — {url.split('/')[-2:]}")
            return None
        return resp.json()
    except requests.exceptions.RequestException as exc:
        print(f"    Request failed: {exc}")
        return None


# ── Checkpoint management ─────────────────────────────────────────────────────

def load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH) as fh:
            return json.load(fh)
    return {
        "completed_leagues": [],
        "processed_fixture_ids": [],
        "h2h_cache": {},           # "min_max" → {"wins_a": N, "wins_b": N, "draws": N}
        "total_call_count": 0,
    }


def save_checkpoint(cp: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CHECKPOINT_PATH, "w") as fh:
        json.dump(cp, fh, indent=2)


# ── Standings fetcher ──────────────────────────────────────────────────────────

def fetch_standings(season_id: int, call_count: list) -> dict[int, dict]:
    """
    Fetch standings via existing get_season_standings (reuses storage layer).
    Returns team_id → {position, goals_scored, goals_against, form}.
    Counts 1 API call before delegating to the storage function.
    """
    call_count[0] += 1  # get_season_standings makes 1 HTTP request internally
    result = get_season_standings(season_id)
    if result["status"] != "success":
        print(f"    standings error: {result.get('message', 'unknown')}")
        return {}

    standings: dict[int, dict] = {}
    for row in result.get("data", []):
        tid = row.get("participant_id")
        if not tid:
            continue
        standings[tid] = {
            "position":      row.get("position"),
            "goals_scored":  row.get("goals_scored"),
            "goals_against": row.get("goals_against"),
            "form":          row.get("form") or "",
        }
    return standings


# ── Season fixture fetcher ────────────────────────────────────────────────────

def fetch_season_fixtures(
    league_id: int, api_key: str, call_count: list
) -> list[dict]:
    """
    Paginate /fixtures/between/{date_from}/{date_to} filtered by league_id.
    Uses the confirmed-working endpoint from backtest.py (Starter tier compatible).
    Returns raw fixture dicts for completed matches (result_info present).
    Stops early if DAILY_CALL_BUDGET is reached.
    """
    url = f"{BASE_URL}/fixtures/between/{SEASON_DATE_FROM}/{SEASON_DATE_TO}"
    all_fixtures: list[dict] = []

    for page in range(1, 500):  # wide upper bound — pagination loop
        if call_count[0] >= DAILY_CALL_BUDGET:
            print(f"    Budget cap reached at page {page} — stopping early")
            break

        params = {
            "api_token": api_key,
            "filters":   f"leagueIds:{league_id}",
            "include":   "scores;participants",
            "per_page":  25,
            "page":      page,
        }
        body = _get(url, params, call_count)
        if body is None:
            break

        data = body.get("data", [])
        if not data:
            break  # no more pages

        completed = [f for f in data if f.get("result_info")]
        all_fixtures.extend(completed)
        print(f"    Page {page}: {len(data)} fixtures, {len(completed)} completed "
              f"(call {call_count[0]}/{DAILY_CALL_BUDGET})")

        # SportMonks caps at 25 per page on this subscription tier
        if len(data) < 25:
            break

    return all_fixtures


# ── Parsing helpers ───────────────────────────────────────────────────────────

def parse_scores(scores_list: list) -> tuple[int | None, int | None]:
    """
    Extract (home_goals, away_goals) from a SportMonks scores include array.
    Prefers "2ND_HALF" description (confirmed full-time label from backtest.py).
    Falls back to "CURRENT" then "FULLTIME" if 2ND_HALF is absent.
    Returns (None, None) if scores unavailable.
    """
    if not scores_list:
        return None, None

    def _extract(desc: str) -> tuple[int | None, int | None]:
        home_g = away_g = None
        for entry in scores_list:
            if entry.get("description") != desc:
                continue
            score_obj = entry.get("score") or {}
            goals     = score_obj.get("goals")
            side      = score_obj.get("participant", "").lower()
            if goals is not None:
                if side == "home":
                    home_g = goals
                elif side == "away":
                    away_g = goals
        if home_g is not None and away_g is not None:
            return home_g, away_g
        return None, None

    for desc in ("2ND_HALF", "CURRENT", "FULLTIME"):
        home_g, away_g = _extract(desc)
        if home_g is not None:
            return home_g, away_g

    return None, None


def parse_participants(fixture: dict) -> tuple[int | None, int | None]:
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


def derive_outcome(home_goals: int, away_goals: int) -> str:
    """Functional oracle: derive outcome directly from ground-truth goals."""
    if home_goals > away_goals:
        return "home_win"
    if home_goals == away_goals:
        return "draw"
    return "away_win"


# ── H2H fetcher ───────────────────────────────────────────────────────────────

def fetch_h2h_counts(
    team_a_id: int, team_b_id: int, api_key: str, call_count: list
) -> dict:
    """
    Fetch head-to-head history and count wins for each team plus draws.
    Calls /fixtures/head-to-head/{a}/{b}?include=scores;participants.
    Returns {"wins_a": N, "wins_b": N, "draws": N} where team_a is the lower ID.
    Returns zeros on API error rather than failing the row.
    """
    # Canonical order: always store lower ID first so pair is keyed consistently
    low_id, high_id = sorted([team_a_id, team_b_id])
    url = f"{BASE_URL}/fixtures/head-to-head/{low_id}/{high_id}"

    body = _get(url, {"api_token": api_key, "include": "scores;participants"}, call_count)
    if body is None:
        return {"wins_a": 0, "wins_b": 0, "draws": 0}

    counts = {"wins_a": 0, "wins_b": 0, "draws": 0}
    for fixture in (body.get("data") or []):
        if not fixture.get("result_info"):
            continue  # skip incomplete H2H fixtures
        home_id, away_id = parse_participants(fixture)
        home_g, away_g = parse_scores(fixture.get("scores") or [])
        if home_g is None or away_g is None:
            continue
        outcome = derive_outcome(home_g, away_g)
        if outcome == "draw":
            counts["draws"] += 1
        elif outcome == "home_win":
            winner_id = home_id
            if winner_id == low_id:
                counts["wins_a"] += 1
            elif winner_id == high_id:
                counts["wins_b"] += 1
        else:  # away_win
            winner_id = away_id
            if winner_id == low_id:
                counts["wins_a"] += 1
            elif winner_id == high_id:
                counts["wins_b"] += 1

    return counts


# ── CSV writer ────────────────────────────────────────────────────────────────

def write_rows(rows: list[dict], append: bool) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    mode = "a" if append else "w"
    with open(CSV_PATH, mode, newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        if not append:
            writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in CSV_COLUMNS})


# ── Main ───────────────────────────────────────────────────────────────────────

def run() -> None:
    api_key    = _api_key()
    call_count = [0]  # mutable so helpers can increment it

    print("=== DATA PULL — AI SPORTS PREDICTOR ===")
    print(f"Date: {__import__('datetime').date.today()} | Session budget: {DAILY_CALL_BUDGET} calls")
    print("Known season IDs loaded — 0 discovery calls used.\n")

    cp = load_checkpoint()
    call_count[0] = cp.get("total_call_count", 0)
    csv_exists    = os.path.exists(CSV_PATH)
    completed_leagues    = set(cp.get("completed_leagues", []))
    processed_fixture_ids = set(cp.get("processed_fixture_ids", []))
    h2h_cache    = cp.get("h2h_cache", {})

    total_saved = 0

    for league_id, meta in KNOWN_SEASONS.items():
        season_id = meta["season_id"]
        name      = meta["name"]

        if league_id in completed_leagues:
            print(f"[League {league_id} — {name}]")
            print("  Already completed — skipping.\n")
            continue

        if call_count[0] >= DAILY_CALL_BUDGET:
            print(f"[League {league_id} — {name}]")
            print(f"  Budget cap reached ({call_count[0]}/{DAILY_CALL_BUDGET}) — stopping session.")
            break

        print(f"[League {league_id} — {name}]")

        # ── Standings (1 call) ─────────────────────────────────────────────────
        print(f"  Standings... (call {call_count[0] + 1}/{DAILY_CALL_BUDGET})")
        standings = fetch_standings(season_id, call_count)
        if not standings:
            print("  No standings data — skipping league.")
            continue

        # ── Season fixtures (paginated) ────────────────────────────────────────
        print(f"  Fetching fixtures for season {season_id}...")
        raw_fixtures = fetch_season_fixtures(league_id, api_key, call_count)

        completed_here = [
            f for f in raw_fixtures
            if f.get("id") not in processed_fixture_ids
        ]
        print(f"  {len(raw_fixtures)} completed fixtures total, "
              f"{len(completed_here)} new (not in checkpoint)")

        if not completed_here:
            print("  No new fixtures — marking league complete.\n")
            completed_leagues.add(league_id)
            cp["completed_leagues"] = list(completed_leagues)
            save_checkpoint(cp)
            continue

        # ── H2H + row assembly ─────────────────────────────────────────────────
        unique_pairs: set[str] = set()
        for f in completed_here:
            home_id, away_id = parse_participants(f)
            if home_id and away_id:
                low, high = sorted([home_id, away_id])
                unique_pairs.add(f"{low}_{high}")

        new_pairs = [p for p in unique_pairs if p not in h2h_cache]
        print(f"  H2H fetching — {len(new_pairs)} new pairs "
              f"({len(unique_pairs) - len(new_pairs)} cached)...")

        for pair_key in new_pairs:
            if call_count[0] >= DAILY_CALL_BUDGET:
                print(f"  Budget cap hit during H2H fetch — saving and exiting.")
                cp["h2h_cache"]        = h2h_cache
                cp["total_call_count"] = call_count[0]
                save_checkpoint(cp)
                _print_summary(call_count[0], total_saved)
                return

            a_id, b_id = (int(x) for x in pair_key.split("_"))
            counts = fetch_h2h_counts(a_id, b_id, api_key, call_count)
            h2h_cache[pair_key] = counts

        # ── Build CSV rows ─────────────────────────────────────────────────────
        rows: list[dict] = []
        skipped = 0

        for f in completed_here:
            fid     = f.get("id")
            home_id, away_id = parse_participants(f)
            if not home_id or not away_id:
                skipped += 1
                continue

            home_g, away_g = parse_scores(f.get("scores") or [])
            if home_g is None or away_g is None:
                skipped += 1
                continue

            home_st = standings.get(home_id)
            away_st = standings.get(away_id)
            if not home_st or not away_st:
                skipped += 1
                continue

            low, high   = sorted([home_id, away_id])
            pair_key    = f"{low}_{high}"
            h2h         = h2h_cache.get(pair_key, {"wins_a": 0, "wins_b": 0, "draws": 0})
            is_home_low = home_id == low  # True when home team is the "a" team in cache key

            rows.append({
                "fixture_id":               fid,
                "league_id":                league_id,
                "season_id":                season_id,
                "match_date":               (f.get("starting_at") or "")[:10],
                "home_team_id":             home_id,
                "away_team_id":             away_id,
                "home_goals":               home_g,
                "away_goals":               away_g,
                "actual_outcome":           derive_outcome(home_g, away_g),
                "home_standing_pos":        home_st["position"],
                "away_standing_pos":        away_st["position"],
                "home_goals_scored_season": home_st["goals_scored"],
                "home_goals_conceded_season": home_st["goals_against"],
                "away_goals_scored_season": away_st["goals_scored"],
                "away_goals_conceded_season": away_st["goals_against"],
                "home_form_last5":          (home_st["form"] or "")[:5],
                "h2h_home_wins": h2h["wins_a"] if is_home_low else h2h["wins_b"],
                "h2h_away_wins": h2h["wins_b"] if is_home_low else h2h["wins_a"],
                "h2h_draws":                h2h["draws"],
            })

        if rows:
            write_rows(rows, append=csv_exists)
            csv_exists = True
            total_saved += len(rows)
            print(f"  Done — {len(rows)} rows saved to CSV "
                  f"({skipped} skipped — missing data)")

            processed_fixture_ids.update(r["fixture_id"] for r in rows)
            cp["processed_fixture_ids"] = list(processed_fixture_ids)
        else:
            print(f"  0 rows written ({skipped} skipped — missing scores/standings)")

        # ── Checkpoint after each league ───────────────────────────────────────
        completed_leagues.add(league_id)
        cp["completed_leagues"] = list(completed_leagues)
        cp["h2h_cache"]        = h2h_cache
        cp["total_call_count"] = call_count[0]
        save_checkpoint(cp)
        print()

    _print_summary(call_count[0], total_saved)


def _print_summary(call_count: int, total_saved: int) -> None:
    print("SESSION SUMMARY")
    print(f"Calls used this session: {call_count}/{DAILY_CALL_BUDGET}")
    print(f"Total fixtures saved: {total_saved}")
    print(f"CSV: {CSV_PATH}")
    print(f"Checkpoint: {CHECKPOINT_PATH}")
    if call_count >= DAILY_CALL_BUDGET:
        print("Run again tomorrow to continue if incomplete.")


if __name__ == "__main__":
    run()
