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
