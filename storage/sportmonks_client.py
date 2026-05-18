import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.sportmonks.com/v3/football"
API_KEY = os.getenv("SPORTMONKS_API_KEY") or ""

def _auth_headers() -> dict:
    """Return Authorization headers using the current env value (re-read on each call)."""
    key = os.getenv("SPORTMONKS_API_KEY") or API_KEY
    return {"Authorization": key} if key else {}

HEADERS = _auth_headers()

# League IDs from SportMonks v3
LEAGUE_IDS = {
    "premier_league": 8,
    "ligue_1": 301,
    "la_liga": 564,
    "serie_a": 384,
    "bundesliga": 82,
    "mls": 779,
}

# All leagues to include when filtering the date-range response.
# Filtering happens in Python because SportMonks leagueId path filters
# are not supported on all subscription tiers.
FETCH_LEAGUE_IDS: set[int] = {
    LEAGUE_IDS["mls"],            # 779
    LEAGUE_IDS["premier_league"], # 8
    LEAGUE_IDS["la_liga"],        # 564
    LEAGUE_IDS["serie_a"],        # 384
    LEAGUE_IDS["bundesliga"],     # 82
    LEAGUE_IDS["ligue_1"],        # 301
}

# Human-readable names keyed by league ID
LEAGUE_NAMES: dict[int, str] = {
    LEAGUE_IDS["premier_league"]: "Premier League",
    LEAGUE_IDS["ligue_1"]:        "Ligue 1",
    LEAGUE_IDS["la_liga"]:        "La Liga",
    LEAGUE_IDS["serie_a"]:        "Serie A",
    LEAGUE_IDS["bundesliga"]:     "Bundesliga",
    LEAGUE_IDS["mls"]:            "Major League Soccer",
}


def get_team_stats(team_id: int) -> dict:
    """Fetch basic team info and stats by team ID."""
    try:
        url = f"{BASE_URL}/teams/{team_id}"
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        return {"status": "success", "data": resp.json().get("data", {})}
    except requests.exceptions.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Request failed: {e}"}


def get_head_to_head(team_a_id: int, team_b_id: int) -> dict:
    """Fetch head-to-head fixture history between two teams."""
    try:
        url = f"{BASE_URL}/fixtures/head-to-head/{team_a_id}/{team_b_id}"
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        return {"status": "success", "data": resp.json().get("data", [])}
    except requests.exceptions.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Request failed: {e}"}


def get_recent_fixtures(team_id: int, limit: int = 5) -> dict:
    """Fetch recent fixtures for a team to evaluate recent form."""
    endpoints = [
        (f"{BASE_URL}/fixtures", {"filters": f"teamId:{team_id}"}),
        (f"{BASE_URL}/fixtures/upcoming/teamId/{team_id}", {}),
        (f"{BASE_URL}/fixtures/latest/teamId/{team_id}", {}),
    ]

    last_error = None
    for url, params in endpoints:
        try:
            resp = requests.get(url, headers=HEADERS, params=params)
            resp.raise_for_status()
            data = resp.json().get("data", [])
            if data:
                return {"status": "success", "data": data[:limit]}
        except requests.exceptions.HTTPError as e:
            last_error = f"HTTP error: {e}"
        except requests.exceptions.RequestException as e:
            last_error = f"Request failed: {e}"

    return {"status": "error", "message": last_error or "All endpoints failed"}


def check_team_data(team_a_id: int, team_b_id: int) -> dict:
    """Verify both teams exist and have accessible data."""
    result_a = get_team_stats(team_a_id)
    result_b = get_team_stats(team_b_id)

    team_a_ready = result_a["status"] == "success" and bool(result_a["data"])
    team_b_ready = result_b["status"] == "success" and bool(result_b["data"])

    if not team_a_ready or not team_b_ready:
        return {"status": "team_not_found"}

    return {
        "status": "success",
        "data": {"team_a_ready": team_a_ready, "team_b_ready": team_b_ready},
    }


def _parse_scores(scores_list: list) -> dict | None:
    """Extract home/away goals from a SportMonks scores include array.

    SportMonks returns one score entry per team per description type.
    We prefer description == "CURRENT" (live / final score).
    Fallback: "2ND_HALF" which also represents the full-time tally.

    Returns {"home": int, "away": int} or None if no score data found.
    """
    if not scores_list:
        return None

    def extract(description: str) -> dict | None:
        home_goals = None
        away_goals = None
        for entry in scores_list:
            if entry.get("description") != description:
                continue
            score_obj = entry.get("score") or {}
            goals = score_obj.get("goals")
            participant = score_obj.get("participant", "").lower()
            if goals is not None:
                if participant == "home":
                    home_goals = goals
                elif participant == "away":
                    away_goals = goals
        if home_goals is not None and away_goals is not None:
            return {"home": home_goals, "away": away_goals}
        return None

    for desc in ("CURRENT", "2ND_HALF", "FULLTIME"):
        result = extract(desc)
        if result is not None:
            return result

    return None


def _fetch_upcoming_per_league(api_key: str) -> list[dict]:
    """Try /fixtures/upcoming/leagueId/{id} then /fixtures/date/{date} fallbacks.

    Some plans don't support the date-range endpoint for future fixtures.
    Returns a combined list of raw SportMonks fixture dicts (may be empty).
    """
    from datetime import date, timedelta

    params_base = {
        "api_token": api_key,
        "include": "participants;league;state;scores;venue",
        "per_page": 100,
    }
    combined: list[dict] = []
    seen_ids: set = set()

    def _add(fixtures: list[dict]) -> None:
        for f in fixtures:
            fid = f.get("id")
            if fid is None:
                continue  # skip malformed fixtures with no ID
            if fid not in seen_ids:
                seen_ids.add(fid)
                combined.append(f)

    def _safe_json(resp: requests.Response) -> list[dict]:
        try:
            return resp.json().get("data", [])
        except ValueError:
            print(f"[SportMonks] Non-JSON response ({resp.status_code}), body: {resp.text[:200]}")
            return []

    # Strategy A: per-league upcoming endpoint
    league_upcoming_ok = False
    for league_id in FETCH_LEAGUE_IDS:
        url = f"{BASE_URL}/fixtures/upcoming/leagueId/{league_id}"
        try:
            resp = requests.get(url, params=params_base, timeout=15)
            if not resp.ok:
                print(f"[SportMonks] upcoming/leagueId/{league_id}: HTTP {resp.status_code}")
                continue
            fixtures = _safe_json(resp)
            print(f"[SportMonks] upcoming/leagueId/{league_id}: {len(fixtures)} fixtures")
            if fixtures:
                league_upcoming_ok = True
                _add(fixtures)
        except requests.exceptions.RequestException as exc:
            print(f"[SportMonks] upcoming/leagueId/{league_id} failed: {exc}")

    if league_upcoming_ok:
        return combined

    # Strategy B: /fixtures/date/{YYYY-MM-DD} for today + tomorrow
    print("[SportMonks] Trying /fixtures/date/{date} for today and tomorrow")
    for offset in (0, 1):
        target = date.today() + timedelta(days=offset)
        url = f"{BASE_URL}/fixtures/date/{target}"
        try:
            resp = requests.get(url, params=params_base, timeout=15)
            if not resp.ok:
                print(f"[SportMonks] /fixtures/date/{target}: HTTP {resp.status_code}")
                continue
            all_day = _safe_json(resp)
            day_filtered = [f for f in all_day if f.get("league_id") in FETCH_LEAGUE_IDS]
            print(f"[SportMonks] /fixtures/date/{target}: {len(all_day)} total, {len(day_filtered)} in our leagues")
            _add(day_filtered)
        except requests.exceptions.RequestException as exc:
            print(f"[SportMonks] /fixtures/date/{target} failed: {exc}")

    return combined


def get_upcoming_mls_fixtures() -> dict:
    """Fetch fixtures across all FETCH_LEAGUE_IDS.

    Strategy:
    1. Try /fixtures/between/{start}/{end} (14 days back → 60 days ahead).
    2. If that returns only past fixtures (all starting_at < today), also try
       /fixtures/upcoming/leagueId/{id} per league and merge the results.
       This handles subscription plans where the date-range endpoint only
       returns completed matches.

    Includes: participants, league, state, scores, venue.
    """
    from datetime import date, timedelta

    api_key = os.getenv("SPORTMONKS_API_KEY") or API_KEY

    key_set = bool(api_key)
    key_len = len(api_key) if api_key else 0
    print(f"[SportMonks] SPORTMONKS_API_KEY set: {key_set}, length: {key_len}")

    if not api_key:
        msg = "SPORTMONKS_API_KEY is not set — add it to .env and restart the server"
        print(f"[SportMonks] ERROR: {msg}")
        return {"status": "error", "message": msg}

    # ── Step 1: date-range endpoint ────────────────────────────────────────────
    start_date = date.today() - timedelta(days=14)
    end_date = date.today() + timedelta(days=60)
    url = f"{BASE_URL}/fixtures/between/{start_date}/{end_date}"

    params = {
        "api_token": api_key,
        "include": "participants;league;state;scores;venue",
        "per_page": 500,
    }

    safe_path = f"/v3/football/fixtures/between/{start_date}/{end_date}"
    safe_params = [k for k in params if k != "api_token"]
    print(f"[SportMonks] Trying: {safe_path}  params={safe_params}")

    date_range_fixtures: list[dict] = []
    date_range_error: str | None = None

    try:
        resp = requests.get(url, params=params, timeout=20)
        print(f"[SportMonks] HTTP status: {resp.status_code}")

        if not resp.ok:
            try:
                body = resp.json()
                sm_msg = body.get("message") or body.get("error") or str(body)
            except Exception:
                sm_msg = resp.text[:300]
            print(f"[SportMonks] Error body: {sm_msg}")
            if resp.status_code == 403:
                date_range_error = (
                    f"HTTP 403 Forbidden on {safe_path} — "
                    "your SportMonks plan may not include fixture date-range access. "
                    f"SportMonks says: {sm_msg}"
                )
            else:
                date_range_error = f"HTTP {resp.status_code} on {safe_path}"
        else:
            try:
                body = resp.json()
            except ValueError:
                body = {}
                print(f"[SportMonks] Non-JSON 200 response from {safe_path}")
            all_fixtures = body.get("data", [])
            print(f"[SportMonks] Total fixtures in date-range response: {len(all_fixtures)}")
            date_range_fixtures = [
                f for f in all_fixtures
                if f.get("league_id") in FETCH_LEAGUE_IDS
            ]
            print(f"[SportMonks] After league filter: {len(date_range_fixtures)}")

    except requests.exceptions.RequestException as exc:
        date_range_error = f"Request failed for {safe_path}: {exc}"
        print(f"[SportMonks] {date_range_error}")

    # ── Step 2: check if date-range has any upcoming fixtures ──────────────────
    today_str = str(date.today())
    has_upcoming = any(
        (f.get("starting_at") or "") >= today_str
        for f in date_range_fixtures
    )

    upcoming_fixtures: list[dict] = []
    if not has_upcoming:
        print(
            "[SportMonks] Date-range returned no upcoming fixtures — "
            "trying /fixtures/upcoming/leagueId/{id} per league"
        )
        upcoming_fixtures = _fetch_upcoming_per_league(api_key)
        print(f"[SportMonks] Per-league upcoming total: {len(upcoming_fixtures)}")

    # ── Merge: deduplicate by fixture ID ──────────────────────────────────────
    seen: set[int] = set()
    merged: list[dict] = []
    for f in date_range_fixtures + upcoming_fixtures:
        fid = f.get("id")
        if fid is None:
            continue
        if fid not in seen:
            seen.add(fid)
            merged.append(f)

    found_leagues: dict[int, int] = {}
    for f in merged:
        lid = f.get("league_id", 0)
        found_leagues[lid] = found_leagues.get(lid, 0) + 1
    print(f"[SportMonks] Final league breakdown: {found_leagues}")

    if not merged:
        msg = date_range_error or (
            f"Date-range ({start_date} → {end_date}) returned "
            f"0 fixtures matching league IDs {FETCH_LEAGUE_IDS}. "
            "Check league IDs or subscription."
        )
        return {"status": "error", "message": msg}

    merged.sort(key=lambda f: f.get("starting_at") or "")
    return {"status": "success", "data": merged}


def get_fixture_detail(fixture_id: int) -> dict:
    """Fetch a single fixture by ID with participant and score data."""
    try:
        url = f"{BASE_URL}/fixtures/{fixture_id}"
        resp = requests.get(
            url,
            headers=HEADERS,
            params={"include": "participants;scores;state"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return {"status": "success", "data": data}
    except requests.exceptions.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Request failed: {e}"}


def get_latest_fixtures(team_id: int, limit: int = 5) -> dict:
    """Fetch the last N completed fixtures for a team."""
    try:
        url = f"{BASE_URL}/fixtures/latest/teamId/{team_id}"
        resp = requests.get(url, headers=_auth_headers(), params={"per_page": limit}, timeout=10)
        resp.raise_for_status()
        raw = resp.json().get("data", [])
        parsed = [
            {
                "name": f.get("name", ""),
                "starting_at": (f.get("starting_at") or "")[:10],
                "result_info": f.get("result_info") or "",
            }
            for f in raw[:limit]
        ]
        return {"status": "success", "data": parsed}
    except requests.exceptions.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Request failed: {e}"}


def get_season_standings(season_id: int) -> dict:
    """Fetch full standings table for a season with team names and W/D/L details."""
    if not season_id:
        return {"status": "error", "message": "season_id required"}
    # Standings detail type_ids (confirmed from API)
    _TID = {
        "played":   129,
        "won":      130,
        "draw":     131,
        "lost":     132,
        "goals_scored":   133,
        "goals_against":  134,
        "goal_diff":      179,
    }
    try:
        url = f"{BASE_URL}/standings/seasons/{season_id}"
        resp = requests.get(
            url, headers=_auth_headers(),
            params={"include": "participant;details"},
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json().get("data", [])

        parsed = []
        for row in raw:
            participant = row.get("participant") or {}

            # Build a type_id → value map from the details array
            details_map: dict[int, int] = {}
            for det in (row.get("details") or []):
                tid = det.get("type_id")
                val = det.get("value")
                if tid is not None and isinstance(val, (int, float)):
                    details_map[tid] = int(val)

            parsed.append({
                "position":       row.get("position"),
                "participant_id": row.get("participant_id"),
                "team_name":      participant.get("name", ""),
                "team_logo":      participant.get("image_path"),
                "points":         row.get("points"),
                "won":            details_map.get(_TID["won"]),
                "drawn":          details_map.get(_TID["draw"]),
                "lost":           details_map.get(_TID["lost"]),
                "goals_scored":   details_map.get(_TID["goals_scored"]),
                "goals_against":  details_map.get(_TID["goals_against"]),
                "goal_difference":details_map.get(_TID["goal_diff"]),
                "total_played":   details_map.get(_TID["played"]),
                "form":           row.get("form"),
            })
        return {"status": "success", "data": parsed}
    except requests.exceptions.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Request failed: {e}"}


def get_team_season_stats(team_id: int, season_id: int) -> dict:
    """Fetch season statistics for a specific team."""
    if not season_id:
        return {"status": "error", "message": "season_id required"}
    try:
        url = f"{BASE_URL}/statistics/seasons/teams/{team_id}"
        resp = requests.get(
            url, headers=_auth_headers(),
            params={"filters": f"seasonId:{season_id}"},
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json().get("data", {})

        # Normalise: may be a list or a single object
        stat = (raw[0] if isinstance(raw, list) and raw else raw) or {}
        details = stat.get("details") or stat

        def _pick(*keys):
            for k in keys:
                v = details.get(k)
                if v is not None:
                    return v
                v = stat.get(k)
                if v is not None:
                    return v
            return None

        goals_scored = _pick("goals_scored", "scored", "goals_for")
        goals_conceded = _pick("goals_conceded", "conceded", "goals_against")
        clean_sheets = _pick("clean_sheets", "cleansheets")
        wins = _pick("wins", "won")
        draws = _pick("draws", "drawn", "draw")
        losses = _pick("losses", "lost")
        total = _pick("total_matches", "played", "games_played")
        avg = round(goals_scored / total, 2) if goals_scored and total else None

        return {
            "status": "success",
            "data": {
                "goals_scored": goals_scored,
                "goals_conceded": goals_conceded,
                "clean_sheets": clean_sheets,
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "total_matches": total,
                "avg_goals_per_game": avg,
            },
        }
    except requests.exceptions.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Request failed: {e}"}


def get_fixture_injuries(fixture_id: int) -> dict:
    """Fetch injured and suspended players for a fixture.

    Returns an empty list (not an error) when the endpoint is not available
    on the current subscription plan (404) so the UI shows "Full squad available".
    """
    try:
        url = f"{BASE_URL}/injuries/fixtures/{fixture_id}"
        resp = requests.get(url, headers=_auth_headers(), timeout=10)
        if resp.status_code == 404:
            return {"status": "success", "data": []}
        resp.raise_for_status()
        raw = resp.json().get("data", [])

        parsed = []
        for entry in raw:
            player = entry.get("player") or {}
            parsed.append({
                "player_name": (
                    player.get("display_name")
                    or player.get("name")
                    or entry.get("player_name", "Unknown")
                ),
                "team_id": entry.get("team_id"),
                "type": entry.get("type", "injured"),
                "reason": entry.get("reason") or entry.get("description", ""),
            })
        return {"status": "success", "data": parsed}
    except requests.exceptions.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Request failed: {e}"}


def get_fixtures_by_date(date_str: str) -> dict:
    """Fetch completed fixtures for a date with full team, score, and statistics data."""
    # Confirmed type_ids from live API inspection
    _STAT_TYPES: dict[int, str] = {
        42: "shots_total",
        86: "shots_on_target",
        45: "possession",
        80: "passes",
        82: "pass_accuracy",
        34: "corners",
        56: "fouls",
        84: "yellow_cards",
    }
    try:
        url = f"{BASE_URL}/fixtures/date/{date_str}"
        resp = requests.get(
            url, headers=_auth_headers(),
            # per_page=100 is required: the default (~5) only returns a subset
            # of fixtures (typically MLS), silently dropping EPL, La Liga, etc.
            params={"include": "participants;scores;statistics.type", "per_page": 100},
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json().get("data", [])

        parsed = []
        for f in raw:
            if not f.get("result_info"):
                continue  # skip fixtures without a result (not yet played)

            # ── Participants → home / away ────────────────────────────────────
            participants = f.get("participants") or []
            home_p = next(
                (p for p in participants if (p.get("meta") or {}).get("location") == "home"), {}
            )
            away_p = next(
                (p for p in participants if (p.get("meta") or {}).get("location") == "away"), {}
            )
            home_id = home_p.get("id")
            away_id = away_p.get("id")

            # ── Scores → CURRENT description ─────────────────────────────────
            home_goals: int | None = None
            away_goals: int | None = None
            for s in (f.get("scores") or []):
                if s.get("description") == "CURRENT":
                    side = (s.get("score") or {}).get("participant", "")
                    goals = (s.get("score") or {}).get("goals")
                    if side == "home":
                        home_goals = goals
                    elif side == "away":
                        away_goals = goals

            # ── Statistics → type_id + location ──────────────────────────────
            stats_map: dict[str, dict[str, int | None]] = {"home": {}, "away": {}}
            for s in (f.get("statistics") or []):
                tid = s.get("type_id")
                loc = s.get("location")
                if tid in _STAT_TYPES and loc in ("home", "away"):
                    val_obj = s.get("data") or {}
                    val = val_obj.get("value") if isinstance(val_obj, dict) else None
                    stats_map[loc][_STAT_TYPES[tid]] = val

            def _side_stats(loc: str) -> dict | None:
                d = stats_map[loc]
                if not d:
                    return None
                return {k: d.get(k) for k in _STAT_TYPES.values()}

            home_stats = _side_stats("home")
            away_stats = _side_stats("away")

            parsed.append({
                "fixture_id":   f.get("id"),
                "name":         f.get("name", ""),
                "date":         (f.get("starting_at") or "")[:10],
                "home_team":    {"id": home_id, "name": home_p.get("name", ""), "logo": home_p.get("image_path")},
                "away_team":    {"id": away_id, "name": away_p.get("name", ""), "logo": away_p.get("image_path")},
                "score":        {"home": home_goals, "away": away_goals},
                "result_info":  f.get("result_info") or "",
                "participant_ids": [home_id, away_id],
                "general_stats": {"home": home_stats, "away": away_stats} if (home_stats or away_stats) else None,
                "xg_stats":     None,  # xgfixture returns 403 on date endpoint (Starter plan)
            })
        return {"status": "success", "data": parsed}
    except requests.exceptions.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Request failed: {e}"}


def get_fixtures_between_for_team(
    team_id: int, start: str, end: str, limit: int = 5
) -> dict:
    """Fetch the last N completed fixtures for a team using the between endpoint.

    Uses /fixtures/between/{start}/{end}/{team_id} which reliably returns
    fixtures for a specific team regardless of league or game-day pattern.
    Returns results sorted newest-first, capped at `limit`.
    """
    _STAT_TYPES: dict[int, str] = {
        42: "shots_total",
        86: "shots_on_target",
        45: "possession",
        80: "passes",
        82: "pass_accuracy",
        34: "corners",
        56: "fouls",
        84: "yellow_cards",
    }
    try:
        url = f"{BASE_URL}/fixtures/between/{start}/{end}/{team_id}"
        resp = requests.get(
            url, headers=_auth_headers(),
            params={"include": "participants;scores;statistics.type", "per_page": 100},
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json().get("data", [])

        # Sort newest-first so [:limit] takes the most recent matches
        raw_sorted = sorted(raw, key=lambda f: f.get("starting_at") or "", reverse=True)

        parsed: list[dict] = []
        for f in raw_sorted:
            if not f.get("result_info"):
                continue  # skip fixtures not yet completed

            participants = f.get("participants") or []
            home_p = next(
                (p for p in participants if (p.get("meta") or {}).get("location") == "home"), {}
            )
            away_p = next(
                (p for p in participants if (p.get("meta") or {}).get("location") == "away"), {}
            )
            home_id = home_p.get("id")
            away_id = away_p.get("id")

            home_goals: int | None = None
            away_goals: int | None = None
            for s in (f.get("scores") or []):
                if s.get("description") == "CURRENT":
                    side = (s.get("score") or {}).get("participant", "")
                    goals = (s.get("score") or {}).get("goals")
                    if side == "home":
                        home_goals = goals
                    elif side == "away":
                        away_goals = goals

            stats_map: dict[str, dict[str, int | None]] = {"home": {}, "away": {}}
            for s in (f.get("statistics") or []):
                tid = s.get("type_id")
                loc = s.get("location")
                if tid in _STAT_TYPES and loc in ("home", "away"):
                    val_obj = s.get("data") or {}
                    val = val_obj.get("value") if isinstance(val_obj, dict) else None
                    stats_map[loc][_STAT_TYPES[tid]] = val

            def _side(loc: str) -> dict | None:
                d = stats_map[loc]
                return {k: d.get(k) for k in _STAT_TYPES.values()} if d else None

            parsed.append({
                "fixture_id":    f.get("id"),
                "name":          f.get("name", ""),
                "date":          (f.get("starting_at") or "")[:10],
                "home_team":     {"id": home_id, "name": home_p.get("name", ""), "logo": home_p.get("image_path")},
                "away_team":     {"id": away_id, "name": away_p.get("name", ""), "logo": away_p.get("image_path")},
                "score":         {"home": home_goals, "away": away_goals},
                "result_info":   f.get("result_info") or "",
                "participant_ids": [home_id, away_id],
                "general_stats": {"home": _side("home"), "away": _side("away")} if (_side("home") or _side("away")) else None,
                "xg_stats":      None,  # xgfixture is 403 on Starter plan
            })
            if len(parsed) >= limit:
                break

        return {"status": "success", "data": parsed}
    except requests.exceptions.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Request failed: {e}"}


def get_fixture_with_xg(fixture_id: int) -> dict:
    """Fetch a fixture with xG stats and trends included (0 extra API calls via includes)."""
    try:
        url = f"{BASE_URL}/fixtures/{fixture_id}"
        resp = requests.get(
            url, headers=_auth_headers(),
            params={"include": "xGFixture;trends;participants"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})

        # Identify home/away team IDs from participants
        participants = data.get("participants") or []
        home_team_id: int | None = None
        away_team_id: int | None = None
        for p in participants:
            loc = (p.get("meta") or {}).get("location", "")
            if loc == "home":
                home_team_id = p.get("id")
            elif loc == "away":
                away_team_id = p.get("id")

        # Parse xGFixture
        xg_raw = data.get("xGFixture") or []
        if isinstance(xg_raw, dict):
            xg_raw = xg_raw.get("data", [])
        xg: dict | None = None
        if xg_raw:
            entry = xg_raw[0]
            home_xg = entry.get("home_xg")
            away_xg = entry.get("away_xg")
            if home_xg is not None and away_xg is not None:
                xg = {"team_a_xg": float(home_xg), "team_b_xg": float(away_xg)}

        # Parse trends grouped by team
        trends_raw = data.get("trends") or []
        if isinstance(trends_raw, dict):
            trends_raw = trends_raw.get("data", [])
        team_a_trends: list[str] = []
        team_b_trends: list[str] = []
        for trend in trends_raw:
            tid = trend.get("team_id")
            ttype = trend.get("type") or trend.get("name") or ""
            tval = trend.get("value")
            label = f"{ttype}: {tval}" if tval is not None else ttype
            if tid == home_team_id:
                team_a_trends.append(label)
            elif tid == away_team_id:
                team_b_trends.append(label)

        return {
            "status": "success",
            "data": {
                "xg": xg,
                "trends": {"team_a": team_a_trends, "team_b": team_b_trends},
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "season_id": data.get("season_id"),
            },
        }
    except requests.exceptions.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Request failed: {e}"}
