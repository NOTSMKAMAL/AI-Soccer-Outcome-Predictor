#!/usr/bin/env python3
"""
Round statistics pull for rolling form enrichment.

Fetches round-level statistics (endpoint 242) for all 5 leagues and builds
rolling 5-round goals form per team at the time of each fixture in raw_fixtures.csv.

Architecture layer: storage (reads from SportMonks API, local CSV).
Does NOT call: engine/prediction_engine.py, backend/main.py, any FastAPI endpoint, Gemini.

Per CS180 Lecture 8/11: Move expensive work out of request path via offline precomputation.
Per Lab 4 Functionality 2: "Recent form" is an explicit comparison factor.

Run from project root with venv activated:
  python3 scripts/pull_round_stats.py
"""

import csv
import json
import os
import sys
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()


# ── Constants ──────────────────────────────────────────────────────────────────

BASE_URL = "https://api.sportmonks.com/v3/football"
DAILY_CALL_BUDGET = 1500  # hard cap — 500 buffer from 2000/day limit

# Season IDs hardcoded from backtest run
KNOWN_SEASONS: dict[int, dict] = {
    8:   {"season_id": 25583, "name": "Premier League"},
    564: {"season_id": 25659, "name": "La Liga"},
    384: {"season_id": 25533, "name": "Serie A"},
    301: {"season_id": 25651, "name": "Ligue 1"},
    779: {"season_id": 26720, "name": "MLS"},
}

DATA_DIR          = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CSV_PATH          = os.path.join(DATA_DIR, "raw_fixtures.csv")
ENRICHED_PATH     = os.path.join(DATA_DIR, "enriched_fixtures.csv")
CHECKPOINT_PATH   = os.path.join(DATA_DIR, "round_stats_checkpoint.json")


# ── API helpers ────────────────────────────────────────────────────────────────

def _api_key() -> str:
    key = os.getenv("SPORTMONKS_API_KEY") or ""
    if not key:
        print("ERROR: SPORTMONKS_API_KEY is not set — add it to .env and retry.")
        sys.exit(1)
    return key


def _get(url: str, params: dict, call_count: list) -> dict | None:
    """Make one GET request, increment call_count[0], return parsed JSON or None on error."""
    if call_count[0] >= DAILY_CALL_BUDGET:
        print(f"  BUDGET EXHAUSTED — stopping at {call_count[0]} calls")
        return None
    call_count[0] += 1
    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code in (404, 403):
            # Graceful fallback — endpoint may not be available on this tier
            return None
        if not resp.ok:
            print(f"    HTTP {resp.status_code} — {url}")
            return None
        return resp.json()
    except requests.exceptions.RequestException as exc:
        print(f"    Request failed: {exc}")
        return None


# ── Checkpoint management ──────────────────────────────────────────────────────

def load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH) as fh:
            return json.load(fh)
    return {
        "completed_leagues": [],
        "round_lists": {},  # {league_id: [round list]}
        "round_fixtures": {},  # {round_id: {team_id: {scored, conceded}}}
        "round_standings": {},  # {round_id: {team_id: {position, points, ...}}}
        "team_recent_fixtures": {},  # {team_id: [recent fixture list]}
        "upcoming_lineups": {},  # {fixture_id: {home_lineup, away_lineup}}
        "total_call_count": 0,
    }


def save_checkpoint(cp: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CHECKPOINT_PATH, "w") as fh:
        json.dump(cp, fh, indent=2)


# ── Round fetcher ──────────────────────────────────────────────────────────────

def fetch_rounds(season_id: int, api_key: str, call_count: list) -> list[dict]:
    """
    Fetch all rounds for a season via endpoint 197.
    Gracefully returns [] on 404/403 (endpoint may not be available).
    """
    url = f"{BASE_URL}/rounds/seasons/{season_id}"
    params = {
        "api_token": api_key,
        "per_page": 50,
    }
    data = _get(url, params, call_count)
    if not data:
        return []

    rounds = data.get("data", [])
    return rounds


# ── Round fixtures fetcher ────────────────────────────────────────────────────

def fetch_round_fixtures(round_id: int, api_key: str, call_count: list) -> dict:
    """
    Fetch all fixtures for a round via endpoint /rounds/{id}?include=fixtures.scores;fixtures.participants.
    Parse 2ND_HALF scores to get goals scored/conceded per team.
    Returns {team_id: {goals_scored: N, goals_conceded: N}}.
    Gracefully returns {} on 404/403.
    """
    url = f"{BASE_URL}/rounds/{round_id}"
    params = {
        "api_token": api_key,
        "include": "fixtures.scores;fixtures.participants",
    }
    data = _get(url, params, call_count)
    if not data:
        return {}

    fixtures_list = data.get("data", {}).get("fixtures", []) or []
    if not fixtures_list:
        return {}

    result: dict[int, dict] = {}
    for fixture in fixtures_list:
        participants = fixture.get("participants") or []
        scores = fixture.get("scores") or []

        # Find home and away team IDs
        home_team_id = None
        away_team_id = None
        for p in participants:
            meta = p.get("meta") or {}
            if meta.get("location") == "home":
                home_team_id = p.get("id")
            elif meta.get("location") == "away":
                away_team_id = p.get("id")

        if not home_team_id or not away_team_id:
            continue

        # Parse 2ND_HALF scores
        home_goals = 0
        away_goals = 0
        for score in scores:
            if score.get("description") != "2ND_HALF":
                continue
            goals = (score.get("score") or {}).get("goals", 0) or 0
            pid = score.get("participant_id")
            if pid == home_team_id:
                home_goals = int(goals)
            elif pid == away_team_id:
                away_goals = int(goals)

        # Accumulate: home team scored/conceded, away team scored/conceded
        if home_team_id not in result:
            result[home_team_id] = {"goals_scored": 0, "goals_conceded": 0}
        if away_team_id not in result:
            result[away_team_id] = {"goals_scored": 0, "goals_conceded": 0}

        result[home_team_id]["goals_scored"] += home_goals
        result[home_team_id]["goals_conceded"] += away_goals
        result[away_team_id]["goals_scored"] += away_goals
        result[away_team_id]["goals_conceded"] += home_goals

    return result


# ── Round standings fetcher ────────────────────────────────────────────────────

def fetch_round_standings(round_id: int, api_key: str, call_count: list) -> dict:
    """
    Fetch league standings at a specific round via GET /standings/rounds/{round_id}.
    Returns {team_id: {position: N, points: N, goals_scored: N, goals_conceded: N}}.
    Gracefully returns {} on 404/403.
    """
    url = f"{BASE_URL}/standings/rounds/{round_id}"
    params = {
        "api_token": api_key,
    }
    data = _get(url, params, call_count)
    if not data:
        return {}

    standings_list = data.get("data", []) or []
    if not standings_list:
        return {}

    result: dict[int, dict] = {}
    for entry in standings_list:
        team_id = entry.get("participant_id")
        if not team_id:
            continue

        result[team_id] = {
            "position": entry.get("position"),
            "points": entry.get("total_points") or entry.get("points"),
            "goals_scored": entry.get("goals_scored"),
            "goals_conceded": entry.get("goals_against") or entry.get("goals_conceded"),
        }

    return result


# ── Statistics by round fetcher ────────────────────────────────────────────────

def fetch_round_stats(round_id: int, api_key: str, call_count: list) -> dict:
    """
    Fetch statistics for a single round via endpoint 242.
    Returns {team_id: {goals_scored: N, goals_conceded: N}}.
    Gracefully returns {} on 404/403.
    """
    url = f"{BASE_URL}/statistics/rounds/{round_id}"
    params = {
        "api_token": api_key,
        "include": "statistics",
    }
    data = _get(url, params, call_count)
    if not data:
        return {}

    # Parse statistics response
    stats_list = data.get("data", [])
    if not stats_list:
        return {}

    # On first response, print raw structure for visibility
    # This helps verify type_ids match documentation
    if isinstance(stats_list, list) and len(stats_list) > 0:
        print(f"    [First round response sample]")
        print(f"      Round {round_id}: {len(stats_list)} teams")

    result: dict[int, dict] = {}
    for entry in stats_list:
        team_id = entry.get("participant_id")
        if not team_id:
            continue

        # Expected type_ids:
        # type_id 52: goals scored this round
        # type_id 53: goals conceded this round
        stats_arr = entry.get("statistics", [])
        gs = gc = None
        for stat in stats_arr:
            type_id = stat.get("type_id")
            value = stat.get("value")
            if type_id == 52:
                try:
                    gs = int(value or 0)
                except (ValueError, TypeError):
                    pass
            elif type_id == 53:
                try:
                    gc = int(value or 0)
                except (ValueError, TypeError):
                    pass

        if gs is not None and gc is not None:
            result[team_id] = {
                "goals_scored": gs,
                "goals_conceded": gc,
            }

    return result


# ── Form builder ───────────────────────────────────────────────────────────────

def build_form_data(
    raw_fixtures_path: str,
    round_stats: dict,
    all_rounds: dict,
) -> dict:
    """
    For each fixture in raw_fixtures.csv, find the 5 rounds prior and compute
    rolling form stats for each team.

    Returns: {fixture_id: {
        home_form_goals_scored_5r,
        home_form_goals_conceded_5r,
        away_form_goals_scored_5r,
        away_form_goals_conceded_5r
    }}

    Empty string if < 3 rounds available (early season).
    """
    form_data = {}

    with open(raw_fixtures_path) as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            fixture_id = row.get("fixture_id")
            league_id = int(row.get("league_id", 0))
            match_date_str = row.get("match_date", "")
            home_team_id = int(row.get("home_team_id", 0))
            away_team_id = int(row.get("away_team_id", 0))

            if not fixture_id or not league_id or not match_date_str:
                continue

            # Find which round this fixture belongs to
            # Round bounds: starting_at <= match_date < ending_at
            match_date = datetime.fromisoformat(match_date_str).date()
            fixture_round = None

            for rnd in all_rounds.get(league_id, []):
                start_str = rnd.get("starting_at", "")[:10]
                end_str = rnd.get("ending_at", "")[:10]
                if start_str and end_str:
                    start = datetime.fromisoformat(start_str).date()
                    end = datetime.fromisoformat(end_str).date()
                    if start <= match_date <= end:
                        fixture_round = rnd
                        break

            if not fixture_round:
                # Early season — no round found
                form_data[fixture_id] = {
                    "home_form_goals_scored_5r": "",
                    "home_form_goals_conceded_5r": "",
                    "away_form_goals_scored_5r": "",
                    "away_form_goals_conceded_5r": "",
                }
                continue

            # Get the 5 rounds BEFORE this fixture's round (not including the fixture's round)
            fixture_round_num = fixture_round.get("name", "")
            fixture_round_id = fixture_round.get("id")

            # Find round index
            league_rounds = all_rounds.get(league_id, [])
            fixture_idx = None
            for i, r in enumerate(league_rounds):
                if r.get("id") == fixture_round_id:
                    fixture_idx = i
                    break

            if fixture_idx is None or fixture_idx < 0:
                form_data[fixture_id] = {
                    "home_form_goals_scored_5r": "",
                    "home_form_goals_conceded_5r": "",
                    "away_form_goals_scored_5r": "",
                    "away_form_goals_conceded_5r": "",
                }
                continue

            # Get the 5 rounds before (indices fixture_idx-5 to fixture_idx-1)
            prior_rounds = league_rounds[max(0, fixture_idx - 5):fixture_idx]

            if len(prior_rounds) < 3:
                # Early season — not enough rounds yet
                form_data[fixture_id] = {
                    "home_form_goals_scored_5r": "",
                    "home_form_goals_conceded_5r": "",
                    "away_form_goals_scored_5r": "",
                    "away_form_goals_conceded_5r": "",
                }
                continue

            # Compute rolling form for home and away teams
            home_gs = home_gc = away_gs = away_gc = 0
            rounds_used_home = rounds_used_away = 0

            for prior_round in prior_rounds:
                prior_round_id = prior_round.get("id")
                if not prior_round_id:
                    continue

                round_stats_data = round_stats.get(str(prior_round_id), {})

                # Home team (team_ids stored as strings in round_fixtures)
                home_stats = round_stats_data.get(str(home_team_id))
                if home_stats:
                    home_gs += home_stats.get("goals_scored", 0)
                    home_gc += home_stats.get("goals_conceded", 0)
                    rounds_used_home += 1

                # Away team (team_ids stored as strings in round_fixtures)
                away_stats = round_stats_data.get(str(away_team_id))
                if away_stats:
                    away_gs += away_stats.get("goals_scored", 0)
                    away_gc += away_stats.get("goals_conceded", 0)
                    rounds_used_away += 1

            # Store results (empty string if insufficient data)
            form_data[fixture_id] = {
                "home_form_goals_scored_5r": home_gs if rounds_used_home >= 3 else "",
                "home_form_goals_conceded_5r": home_gc if rounds_used_home >= 3 else "",
                "away_form_goals_scored_5r": away_gs if rounds_used_away >= 3 else "",
                "away_form_goals_conceded_5r": away_gc if rounds_used_away >= 3 else "",
                "home_form_rounds_used": str(rounds_used_home) if rounds_used_home >= 3 else "",
                "away_form_rounds_used": str(rounds_used_away) if rounds_used_away >= 3 else "",
            }

    return form_data


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    api_key = _api_key()
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"\n=== ROUND STATS PULL — AI SPORTS PREDICTOR ===")
    print(f"Date: {today} | Budget: {DAILY_CALL_BUDGET} calls\n")

    # Load checkpoint
    checkpoint = load_checkpoint()
    completed = set(checkpoint.get("completed_leagues", []))
    round_lists = checkpoint.get("round_lists", {})
    round_fixtures = checkpoint.get("round_fixtures", {})
    round_standings = checkpoint.get("round_standings", {})
    call_count = [checkpoint.get("total_call_count", 0)]

    # All rounds per league (will populate)
    all_rounds: dict[int, list] = {}

    # ── STEP 1: Fetch rounds per league ────────────────────────────────────────
    print("Step 1: Fetching rounds per league...\n")

    for league_id, season_info in KNOWN_SEASONS.items():
        season_id = season_info["season_id"]
        name = season_info["name"]

        if league_id in completed:
            print(f"[{name}] Already completed — skipping")
            # Restore from checkpoint
            if str(league_id) in round_lists:
                all_rounds[league_id] = round_lists[str(league_id)]
            continue

        print(f"[{name}]")
        print(f"  Fetching rounds for season {season_id}... (call {call_count[0]}/{DAILY_CALL_BUDGET})")

        rounds = fetch_rounds(season_id, api_key, call_count)
        all_rounds[league_id] = rounds
        print(f"  {len(rounds)} rounds found")

        if len(rounds) > 0:
            print(f"  First round: {rounds[0].get('name')} ({rounds[0].get('starting_at', '')[:10]})")

        # ── STEP 2: Fetch fixtures and standings for each round ────────────────
        print(f"  Processing {len(rounds)} rounds...")

        rounds_with_data = 0

        for rnd in rounds:
            round_id = rnd.get("id")
            if not round_id:
                continue

            # Skip if already in checkpoint
            if str(round_id) in round_fixtures and str(round_id) in round_standings:
                rounds_with_data += 1
                continue

            # Fetch round fixtures (2ND_HALF scores)
            r_fixtures = fetch_round_fixtures(round_id, api_key, call_count)
            if r_fixtures:
                round_fixtures[str(round_id)] = r_fixtures
                rounds_with_data += 1

            # Fetch round standings
            r_standings = fetch_round_standings(round_id, api_key, call_count)
            if r_standings:
                round_standings[str(round_id)] = r_standings

        print(f"  League complete: {rounds_with_data} rounds with fixture/standing data")

        # Mark league as completed and save checkpoint
        completed.add(league_id)
        checkpoint["completed_leagues"] = list(completed)
        checkpoint["round_lists"] = {**round_lists, str(league_id): rounds}
        round_lists = checkpoint["round_lists"]  # Update local var for next iteration
        checkpoint["round_fixtures"] = round_fixtures
        checkpoint["round_standings"] = round_standings
        checkpoint["total_call_count"] = call_count[0]
        save_checkpoint(checkpoint)
        print(f"  Checkpoint saved.\n")

    # ── STEP 3: Enrichment phase ───────────────────────────────────────────────
    print("\nENRICHMENT PHASE")
    print(f"  Loading raw_fixtures.csv: {CSV_PATH}")

    # Count fixtures before
    with open(CSV_PATH) as fh:
        fixture_count = sum(1 for _ in csv.DictReader(fh))
    print(f"  {fixture_count} rows")

    print(f"  Computing rolling 5-round form...")

    form_data = build_form_data(CSV_PATH, round_fixtures, all_rounds)

    # Count distribution
    full_data = sum(1 for fd in form_data.values()
                    if fd["home_form_goals_scored_5r"] != "")
    partial_data = sum(1 for fd in form_data.values()
                       if fd["home_form_goals_scored_5r"] == "" and
                          fd.get("away_form_goals_scored_5r") is not None)
    no_data = fixture_count - full_data

    print(f"  Fixtures with full 5-round data: {full_data}")
    print(f"  Fixtures with partial data (1-4 rounds): {partial_data}")
    print(f"  Fixtures with no data (early season): {no_data}")

    # ── STEP 4: Write enriched CSV ─────────────────────────────────────────────
    print(f"\n  Writing enriched CSV...")

    with open(CSV_PATH) as in_fh, open(ENRICHED_PATH, "w", newline="") as out_fh:
        reader = csv.DictReader(in_fh)
        fieldnames = reader.fieldnames or []

        # Add new columns at the end
        new_columns = [
            "home_form_goals_scored_5r",
            "home_form_goals_conceded_5r",
            "away_form_goals_scored_5r",
            "away_form_goals_conceded_5r",
            "home_form_rounds_used",
            "away_form_rounds_used",
        ]
        fieldnames = fieldnames + new_columns

        writer = csv.DictWriter(out_fh, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            fixture_id = row.get("fixture_id")
            fd = form_data.get(fixture_id, {})

            # Add form columns to row
            row["home_form_goals_scored_5r"] = fd.get("home_form_goals_scored_5r", "")
            row["home_form_goals_conceded_5r"] = fd.get("home_form_goals_conceded_5r", "")
            row["away_form_goals_scored_5r"] = fd.get("away_form_goals_scored_5r", "")
            row["away_form_goals_conceded_5r"] = fd.get("away_form_goals_conceded_5r", "")
            row["home_form_rounds_used"] = fd.get("home_form_rounds_used", "")
            row["away_form_rounds_used"] = fd.get("away_form_rounds_used", "")

            writer.writerow(row)

    print(f"  Saved: {ENRICHED_PATH} ({len(fieldnames)} columns)")

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\nSESSION SUMMARY")
    print(f"  Total calls used: {call_count[0]}/{DAILY_CALL_BUDGET}")
    print(f"  Rounds with fixture data: {len(round_fixtures)} across 5 leagues")
    print(f"  Rounds with standings: {len(round_standings)} across 5 leagues")
    print(f"  enriched_fixtures.csv: {fixture_count} rows, {len(fieldnames)} columns")
    print(f"  Ready for Part B: engine rolling form upgrade\n")


if __name__ == "__main__":
    main()
