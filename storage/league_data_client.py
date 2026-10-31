"""football-data.org v4 client for domestic leagues + Champions League.

The single source of live fixture, standings, form and scorer data. Every public
call returns the same `{"status", "data"}` shape that backend/main.py and
engine/prediction_engine.py consume.

Free tier: 10 requests/minute, so every public call is cached and degrades
gracefully (never raises) on error.

Coverage: the five big European leagues plus the Champions League. If a call
fails or no API key is set, backend/main.py serves clearly-flagged demo fixtures
instead of an empty page.
"""
import time
from datetime import date, timedelta

from storage import _fdorg

# ── Competition registry ──────────────────────────────────────────────────────
# football-data.org uses string codes for API paths and integer ids elsewhere.
COMPETITION_CODES: list[str] = ["PL", "BL1", "PD", "SA", "FL1", "CL"]

COMPETITION_NAMES: dict[str, str] = {
    "PL":  "Premier League",
    "BL1": "Bundesliga",
    "PD":  "La Liga",
    "SA":  "Serie A",
    "FL1": "Ligue 1",
    "CL":  "Champions League",
}

# Numeric football-data.org competition ids — used so the frontend `leagueId:number`
# contract keeps working. The string code travels separately as the fixture seasonId.
COMPETITION_IDS: dict[str, int] = {
    "PL":  2021,
    "BL1": 2002,
    "PD":  2014,
    "SA":  2019,
    "FL1": 2015,
    "CL":  2001,
}

# Backwards-compatible exports (some callers/tests imported these names).
LEAGUE_IDS: dict[str, int] = {
    "premier_league": COMPETITION_IDS["PL"],
    "bundesliga":     COMPETITION_IDS["BL1"],
    "la_liga":        COMPETITION_IDS["PD"],
    "serie_a":        COMPETITION_IDS["SA"],
    "ligue_1":        COMPETITION_IDS["FL1"],
    "champions_league": COMPETITION_IDS["CL"],
}
LEAGUE_NAMES: dict[int, str] = {
    COMPETITION_IDS[code]: name for code, name in COMPETITION_NAMES.items()
}

# Map football-data.org match statuses to the lowercase tokens the frontend expects
# (it filters "live"/"inplay"/"halftime" and groups by leagueName).
_STATUS_MAP: dict[str, str] = {
    "SCHEDULED": "upcoming",
    "TIMED":     "upcoming",
    "IN_PLAY":   "live",
    "PAUSED":    "halftime",
    "FINISHED":  "finished",
    "SUSPENDED": "suspended",
    "POSTPONED": "postponed",
    "CANCELLED": "cancelled",
    "AWARDED":   "finished",
}

# ── In-memory TTL caches (10 req/min budget) ──────────────────────────────────
_fixtures_cache:  dict = {}                 # full upcoming list: {"data","ts"}
_standings_cache: dict = {}                 # per competition code: {code: {"data","ts"}}
_team_stats_cache: dict = {}                # per competition code: {code: {"data","ts"}}
_scorers_cache:   dict = {}                 # per competition code: {code: {"data","ts"}}

FIXTURES_TTL   = 120    # 2 minutes — live-ish
STANDINGS_TTL  = 300    # 5 minutes
TEAM_STATS_TTL = 300
SCORERS_TTL    = 3600   # 1 hour — rarely changes


# ── Normalisation ─────────────────────────────────────────────────────────────

def _map_status(raw_status: str) -> str:
    return _STATUS_MAP.get(raw_status, (raw_status or "upcoming").lower())


def _normalize_match(raw: dict, code: str | None = None) -> dict:
    """Convert a football-data.org match object into our internal fixture shape.

    Matches the shape backend/main.py used to produce via `_normalize_fixture`,
    plus a `seasonId` carrying the competition code for downstream stats calls.
    """
    home = raw.get("homeTeam") or {}
    away = raw.get("awayTeam") or {}
    score = raw.get("score") or {}
    full_time = score.get("fullTime") or {}
    comp = raw.get("competition") or {}

    comp_code = code or comp.get("code") or ""
    league_id = COMPETITION_IDS.get(comp_code) or comp.get("id") or 0
    league_name = COMPETITION_NAMES.get(comp_code) or comp.get("name") or comp_code or "League"

    home_name = home.get("name") or home.get("shortName") or "Unknown"
    away_name = away.get("name") or away.get("shortName") or "Unknown"

    venue = raw.get("venue")

    out: dict = {
        "id": str(raw.get("id", "")),
        "name": f"{home_name} vs {away_name}",
        "homeTeam": {"id": home.get("id", 0), "name": home_name},
        "awayTeam": {"id": away.get("id", 0), "name": away_name},
        "startingAt": raw.get("utcDate", ""),
        "leagueId": league_id,
        "leagueName": league_name,
        "seasonId": comp_code,            # competition code → used by standings/stats calls
        "status": _map_status(raw.get("status", "SCHEDULED")),
        "venue": venue,
        "_isMock": False,
    }
    hg, ag = full_time.get("home"), full_time.get("away")
    if hg is not None and ag is not None:
        out["score"] = {"home": hg, "away": ag}
    return out


def _result_info(home_name: str, away_name: str, hg: int | None, ag: int | None) -> str:
    """Build the compact result string the engine's _form_label parses."""
    if hg is None or ag is None:
        return ""
    if hg > ag:
        return f"{home_name} won {hg}-{ag}"
    if ag > hg:
        return f"{away_name} won {ag}-{hg}"
    return f"Draw {hg}-{ag}"


def _parse_scores(scores: dict | None) -> dict | None:
    """Compatibility shim — football-data.org already returns a flat score object."""
    if not scores:
        return None
    ft = scores.get("fullTime") or {}
    hg, ag = ft.get("home"), ft.get("away")
    if hg is None or ag is None:
        return None
    return {"home": hg, "away": ag}


# ── Public API ────────────────────────────────────────────────────────────────

# How many soonest upcoming fixtures to keep per competition (so a full
# next-season schedule of 380 matches doesn't flood the dashboard).
PER_COMPETITION_LIMIT = 12


def get_upcoming_fixtures() -> dict:
    """Fetch the soonest upcoming (and very-recent) fixtures per competition.

    Robust across the season cycle: it asks for each competition's matches over a
    wide forward window (today-3 .. today+180) and keeps the soonest
    PER_COMPETITION_LIMIT non-finished fixtures. This means that even in the
    European off-season — when domestic leagues have no games for weeks — the next
    season's opening fixtures (already published for some competitions) still show
    up, instead of the page falling back to mock data.

    Returns {"status","data":[fixture,...],"source"}.
    """
    global _fixtures_cache
    now = time.time()
    if _fixtures_cache.get("data") and now - _fixtures_cache.get("ts", 0) < FIXTURES_TTL:
        return {"status": "success", "data": _fixtures_cache["data"], "source": "cache"}

    if not _fdorg.has_api_key():
        return {"status": "error", "message": "FOOTBALL_DATA_API_KEY is not set — add it to .env and restart"}

    date_from = str(date.today() - timedelta(days=3))
    date_to = str(date.today() + timedelta(days=180))
    today_str = str(date.today())

    fixtures: list[dict] = []
    errors: list[str] = []
    for code in COMPETITION_CODES:
        res = _fdorg.get(f"/competitions/{code}/matches", {"dateFrom": date_from, "dateTo": date_to})
        if res["status"] != "success":
            errors.append(f"{code}: {res.get('message')}")
            # Back off on rate-limit (free tier: 10 req/min) — stop hammering the
            # API and return whatever competitions already succeeded.
            if res.get("code") == 429 or "429" in str(res.get("message", "")):
                break
            continue
        raw = res["data"].get("matches", [])
        # Keep upcoming/live matches plus anything finished in the last few days;
        # drop the long tail of older finished games.
        upcoming = [m for m in raw
                    if m.get("status") != "FINISHED" or (m.get("utcDate") or "")[:10] >= today_str]
        upcoming.sort(key=lambda m: m.get("utcDate") or "")
        for m in upcoming[:PER_COMPETITION_LIMIT]:
            fixtures.append(_normalize_match(m, code))

    if not fixtures:
        # Partial caching: short-cache an empty list only when the API answered
        # cleanly. On rate-limit/errors, leave the cache empty so the next request
        # retries rather than serving an empty page for the full TTL.
        if not errors:
            _fixtures_cache = {"data": [], "ts": now}
            return {"status": "success", "data": [], "source": "football-data"}
        return {"status": "error", "message": "; ".join(errors) or "No fixtures returned"}

    fixtures.sort(key=lambda f: f.get("startingAt") or "")
    _fixtures_cache = {"data": fixtures, "ts": now}
    return {"status": "success", "data": fixtures, "source": "football-data"}


def get_fixture_detail(fixture_id: int | str) -> dict:
    """Fetch a single match by id, normalized to our fixture shape."""
    res = _fdorg.get(f"/matches/{fixture_id}")
    if res["status"] != "success":
        return res
    raw = res["data"]
    # /matches/{id} nests the match under no wrapper, but be defensive.
    match = raw.get("match") if isinstance(raw, dict) and "match" in raw else raw
    return {"status": "success", "data": _normalize_match(match)}


def _standings_table(code: str) -> list[dict] | None:
    """Fetch and cache the TOTAL standings table for a competition (raw rows)."""
    now = time.time()
    cached = _standings_cache.get(code)
    if cached and now - cached.get("ts", 0) < STANDINGS_TTL:
        return cached["data"]
    if not _fdorg.has_api_key():
        return None
    res = _fdorg.get(f"/competitions/{code}/standings")
    if res["status"] != "success":
        return None
    total = None
    for grp in res["data"].get("standings", []):
        if grp.get("type") == "TOTAL":
            total = grp.get("table", [])
            break
    if total is None:
        groups = res["data"].get("standings", [])
        total = groups[0].get("table", []) if groups else []
    _standings_cache[code] = {"data": total, "ts": now}
    return total


def get_season_standings(season_id: str | int | None) -> dict:
    """Return league standings rows in the engine's expected shape.

    season_id is a football-data.org competition code (e.g. "PL"); the value is
    carried as `seasonId` on each normalized fixture.
    """
    code = str(season_id or "").upper()
    if code not in COMPETITION_NAMES:
        return {"status": "error", "message": f"Unknown competition code: {season_id!r}"}

    table = _standings_table(code)
    if table is None:
        return {"status": "error", "message": f"standings unavailable for {code}"}

    rows: list[dict] = []
    for entry in table:
        team = entry.get("team") or {}
        rows.append({
            "position":        entry.get("position"),
            "participant_id":  team.get("id"),
            "team_name":       team.get("name", ""),
            "points":          entry.get("points"),
            "won":             entry.get("won"),
            "drawn":           entry.get("draw"),
            "lost":            entry.get("lost"),
            "goals_scored":    entry.get("goalsFor"),
            "goals_against":   entry.get("goalsAgainst"),
            "goal_difference": entry.get("goalDifference"),
            "total_played":    entry.get("playedGames"),
            "form":            entry.get("form"),
        })
    return {"status": "success", "data": rows}


def get_season_team_stats(season_id: str | int | None) -> dict:
    """Per-team per-game stats derived from the standings table.

    Returns {team_id: {goals_scored_per_game, goals_conceded_per_game,
    matches_played, clean_sheets}} (raw dict, no envelope) — same shape the engine
    consumed by the engine. clean_sheets is unavailable from standings (0).
    """
    code = str(season_id or "").upper()
    if code not in COMPETITION_NAMES:
        return {}
    table = _standings_table(code)
    if not table:
        return {}

    out: dict[int, dict] = {}
    for entry in table:
        team = entry.get("team") or {}
        team_id = team.get("id")
        played = entry.get("playedGames") or 0
        if not team_id or played <= 0:
            continue
        gf = entry.get("goalsFor") or 0
        ga = entry.get("goalsAgainst") or 0
        out[int(team_id)] = {
            "goals_scored_per_game":   float(gf) / float(played),
            "goals_conceded_per_game": float(ga) / float(played),
            "matches_played":          played,
            "clean_sheets":            0,
        }
    return out


def get_fixtures_between_for_team(team_id: int, start: str, end: str, limit: int = 5) -> dict:
    """Recent finished fixtures for a team (newest first), capped at `limit`.

    Returns the same per-fixture shape the engine's form parser reads, including a
    synthesized `result_info` string.
    """
    res = _fdorg.get(
        f"/teams/{team_id}/matches",
        {"status": "FINISHED", "dateFrom": start, "dateTo": end, "limit": max(limit, 10)},
    )
    if res["status"] != "success":
        return res

    matches = res["data"].get("matches", [])
    matches.sort(key=lambda m: m.get("utcDate") or "", reverse=True)

    parsed: list[dict] = []
    for m in matches:
        home = m.get("homeTeam") or {}
        away = m.get("awayTeam") or {}
        ft = (m.get("score") or {}).get("fullTime") or {}
        hg, ag = ft.get("home"), ft.get("away")
        home_name = home.get("name", "")
        away_name = away.get("name", "")
        parsed.append({
            "fixture_id":      m.get("id"),
            "name":            f"{home_name} vs {away_name}",
            "date":            (m.get("utcDate") or "")[:10],
            "home_team":       {"id": home.get("id"), "name": home_name},
            "away_team":       {"id": away.get("id"), "name": away_name},
            "score":           {"home": hg, "away": ag},
            "result_info":     _result_info(home_name, away_name, hg, ag),
            "participant_ids": [home.get("id"), away.get("id")],
            "general_stats":   None,    # not on free tier
            "xg_stats":        None,    # not on free tier
        })
        if len(parsed) >= limit:
            break
    return {"status": "success", "data": parsed}


def get_recent_fixtures(team_id: int, limit: int = 5) -> dict:
    """Last N finished fixtures for a team (compat wrapper over the between call)."""
    end = str(date.today())
    start = str(date.today() - timedelta(days=120))
    return get_fixtures_between_for_team(team_id, start, end, limit)


def get_head_to_head(team_a_id: int, team_b_id: int) -> dict:
    """Head-to-head history.

    football-data.org exposes H2H only via /matches/{id}/head2head, not by team
    pair, so there is no free way to fetch it ahead of a fixture. Returns an empty
    success list (NOT an error) so the engine's compare_matchup proceeds with its
    "no head-to-head history" branch instead of aborting the prediction.
    """
    return {"status": "success", "data": []}


def get_team_stats(team_id: int) -> dict:
    """Basic team info by id (used by check_team_data)."""
    res = _fdorg.get(f"/teams/{team_id}")
    if res["status"] != "success":
        return res
    return {"status": "success", "data": res["data"]}


def check_team_data(team_a_id: int, team_b_id: int) -> dict:
    """Verify both teams resolve. Best-effort — never blocks the prediction path."""
    a = get_team_stats(team_a_id)
    b = get_team_stats(team_b_id)
    a_ready = a["status"] == "success" and bool(a.get("data"))
    b_ready = b["status"] == "success" and bool(b.get("data"))
    if not a_ready or not b_ready:
        return {"status": "team_not_found"}
    return {"status": "success", "data": {"team_a_ready": a_ready, "team_b_ready": b_ready}}


def get_squad(team_id: int) -> dict:
    """Squad roster for a team. position_id/captain are not on the free tier."""
    res = _fdorg.get(f"/teams/{team_id}")
    if res["status"] != "success":
        return res
    squad = res["data"].get("squad") or []
    parsed = [{
        "player_name":   p.get("name", "Unknown"),
        "position":      p.get("position"),
        "position_id":   None,
        "jersey_number": p.get("shirtNumber"),
        "captain":       False,
    } for p in squad]
    return {"status": "success", "data": parsed}


def get_topscorers_with_names(season_id: str | int | None, limit: int = 10) -> dict:
    """Top scorers for a competition, in the engine's expected shape."""
    code = str(season_id or "").upper()
    if code not in COMPETITION_NAMES:
        return {"status": "error", "message": f"Unknown competition code: {season_id!r}"}

    now = time.time()
    cached = _scorers_cache.get(code)
    if cached and now - cached.get("ts", 0) < SCORERS_TTL:
        return {"status": "success", "data": cached["data"][:limit]}

    res = _fdorg.get(f"/competitions/{code}/scorers", {"limit": max(limit, 10)})
    if res["status"] != "success":
        return res

    parsed: list[dict] = []
    for i, entry in enumerate(res["data"].get("scorers", []), start=1):
        player = entry.get("player") or {}
        team = entry.get("team") or {}
        parsed.append({
            "player_name": player.get("name", "Unknown"),
            "team_name":   team.get("name", ""),
            "team_id":     team.get("id"),
            "goals":       entry.get("goals") or 0,
            "assists":     entry.get("assists") or 0,
            "rank":        i,
        })
    _scorers_cache[code] = {"data": parsed, "ts": now}
    return {"status": "success", "data": parsed[:limit]}


# ── Graceful stubs — data not available on the free tier ──────────────────────

def get_fixture_with_xg(fixture_id: int | str) -> dict:
    """xG / trends are not on the free tier — return a graceful empty payload."""
    return {
        "status": "success",
        "data": {"xg": None, "trends": None, "home_team_id": None,
                 "away_team_id": None, "season_id": None},
    }


def get_fixture_lineups(fixture_id: int | str, team_a_id: int, team_b_id: int) -> dict:
    """Confirmed lineups are not on the free tier — return a graceful empty payload."""
    return {
        "status": "success",
        "data": {"team_a_starters": [], "team_b_starters": [], "confirmed": False},
    }


def get_fixture_injuries(fixture_id: int | str) -> dict:
    """Injuries are not on the free tier — handled by the pluggable injury provider."""
    return {"status": "success", "data": []}
