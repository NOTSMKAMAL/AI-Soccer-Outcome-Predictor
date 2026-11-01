"""Unit tests for storage/league_data_client.py (football-data.org-backed).

The HTTP layer (storage._fdorg) is mocked so these run offline and assert the
normalized shapes that backend/main.py and engine/prediction_engine.py consume.
"""
import os
import sys
from datetime import date, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage import league_data_client as ldc


def setup_function(_fn):
    """Reset module-level TTL caches between tests."""
    ldc._fixtures_cache = {}
    ldc._standings_cache = {}
    ldc._team_stats_cache = {}
    ldc._scorers_cache = {}


# ── Pure normalization ────────────────────────────────────────────────────────

def test_normalize_match_shape():
    raw = {
        "id": 12345,
        "utcDate": "2026-03-01T15:00:00Z",
        "status": "TIMED",
        "homeTeam": {"id": 57, "name": "Arsenal FC", "crest": "a.png"},
        "awayTeam": {"id": 65, "name": "Manchester City", "crest": "b.png"},
        "score": {"fullTime": {"home": None, "away": None}},
        "venue": "Emirates Stadium",
    }
    out = ldc._normalize_match(raw, "PL")
    assert out["id"] == "12345"
    # Crests are copyrighted, so the provider's crest URL must not be passed on.
    assert out["homeTeam"] == {"id": 57, "name": "Arsenal FC"}
    assert out["awayTeam"]["name"] == "Manchester City"
    assert out["leagueId"] == ldc.COMPETITION_IDS["PL"]  # numeric id for frontend
    assert out["leagueName"] == "Premier League"
    assert out["seasonId"] == "PL"                        # code carried for stats calls
    assert out["status"] == "upcoming"                    # TIMED → upcoming
    assert out["_isMock"] is False
    assert "score" not in out                             # no final score yet


def test_normalize_match_with_score_and_live_status():
    raw = {
        "id": 9,
        "utcDate": "2026-03-01T15:00:00Z",
        "status": "IN_PLAY",
        "homeTeam": {"id": 1, "name": "A"},
        "awayTeam": {"id": 2, "name": "B"},
        "score": {"fullTime": {"home": 2, "away": 1}},
    }
    out = ldc._normalize_match(raw, "SA")
    assert out["status"] == "live"
    assert out["score"] == {"home": 2, "away": 1}


def test_result_info_strings():
    assert ldc._result_info("A", "B", 2, 1) == "A won 2-1"
    assert ldc._result_info("A", "B", 0, 3) == "B won 3-0"
    assert ldc._result_info("A", "B", 1, 1) == "Draw 1-1"
    assert ldc._result_info("A", "B", None, None) == ""


# ── Standings → compat rows + per-team stats ──────────────────────────────────

_STANDINGS_PAYLOAD = {
    "status": "success",
    "data": {"standings": [{
        "type": "TOTAL",
        "table": [
            {"position": 1, "team": {"id": 57, "name": "Arsenal", "crest": "c"},
             "playedGames": 10, "won": 7, "draw": 2, "lost": 1,
             "points": 23, "goalsFor": 20, "goalsAgainst": 8,
             "goalDifference": 12, "form": "W,W,D"},
        ],
    }]},
}


def test_get_season_standings_compat_shape():
    with patch.object(ldc._fdorg, "has_api_key", return_value=True), \
         patch.object(ldc._fdorg, "get", return_value=_STANDINGS_PAYLOAD):
        res = ldc.get_season_standings("PL")
    assert res["status"] == "success"
    row = res["data"][0]
    # keys the engine + backend _team_stats_from_standings read
    assert row["participant_id"] == 57
    assert row["total_played"] == 10
    assert row["goals_scored"] == 20
    assert row["goals_against"] == 8
    assert row["won"] == 7 and row["drawn"] == 2 and row["lost"] == 1


def test_get_season_team_stats_per_game():
    with patch.object(ldc._fdorg, "has_api_key", return_value=True), \
         patch.object(ldc._fdorg, "get", return_value=_STANDINGS_PAYLOAD):
        stats = ldc.get_season_team_stats("PL")
    assert 57 in stats
    assert stats[57]["goals_scored_per_game"] == 2.0      # 20 / 10
    assert stats[57]["goals_conceded_per_game"] == 0.8    # 8 / 10
    assert stats[57]["matches_played"] == 10


def test_unknown_competition_is_safe():
    assert ldc.get_season_standings("ZZ")["status"] == "error"
    assert ldc.get_season_team_stats("ZZ") == {}


# ── Upcoming fixtures aggregation ─────────────────────────────────────────────

def _match(code, match_id=1, when="2026-03-01T12:00:00Z", status="SCHEDULED"):
    return {
        "id": match_id,
        "utcDate": when,
        "status": status,
        "competition": {"code": code},
        "homeTeam": {"id": 1, "name": "H"},
        "awayTeam": {"id": 2, "name": "A"},
        "score": {"fullTime": {"home": None, "away": None}},
    }


def _ok(matches):
    return {"status": "success", "data": {"matches": matches}}


def _upcoming(fake_get):
    """Run get_upcoming_fixtures against a fake provider; return (result, paths called)."""
    calls = []

    def recording_get(path, params=None):
        calls.append((path, params or {}))
        return fake_get(path, params)

    with patch.object(ldc._fdorg, "has_api_key", return_value=True), \
         patch.object(ldc._fdorg, "get", side_effect=recording_get):
        return ldc.get_upcoming_fixtures(), calls


def test_get_upcoming_fixtures_aggregates_and_sorts():
    # one match per competition, with deliberately out-of-order dates
    matches = [
        _match(code, i, "2026-03-05T12:00:00Z" if code == "PL" else "2026-03-01T12:00:00Z")
        for i, code in enumerate(ldc.COMPETITION_CODES)
    ]
    res, _ = _upcoming(lambda path, params: _ok(matches))
    assert res["status"] == "success"
    assert res["source"] == "football-data"
    assert len(res["data"]) == len(ldc.COMPETITION_CODES)
    dates = [f["startingAt"] for f in res["data"]]
    assert dates == sorted(dates)                          # sorted ascending


def test_all_six_leagues_come_from_one_call():
    matches = [_match(code, i) for i, code in enumerate(ldc.COMPETITION_CODES)]
    _, calls = _upcoming(lambda path, params: _ok(matches))
    assert len(calls) == 1
    path, params = calls[0]
    assert path == "/matches"
    assert params["competitions"] == ",".join(ldc.COMPETITION_CODES)


def test_combined_window_stays_within_the_ten_day_limit():
    # Measured 2026-10-31: /matches returns HTTP 400 for a 13-day range and 200 for 10.
    matches = [_match(code, i) for i, code in enumerate(ldc.COMPETITION_CODES)]
    _, calls = _upcoming(lambda path, params: _ok(matches))
    params = calls[0][1]
    span = date.fromisoformat(params["dateTo"]) - date.fromisoformat(params["dateFrom"])
    assert span.days <= 10


def test_fixtures_keep_their_own_competition():
    res, _ = _upcoming(lambda path, params: _ok([_match("SA", 7), *[
        _match(code, 10 + i) for i, code in enumerate(ldc.COMPETITION_CODES) if code != "SA"
    ]]))
    fixture = next(f for f in res["data"] if f["id"] == "7")
    assert fixture["seasonId"] == "SA"
    assert fixture["leagueName"] == "Serie A"


def test_quiet_league_gets_its_own_wide_call():
    """Off-season or an international break: only the empty league costs a second call."""
    in_window = [_match(code, i) for i, code in enumerate(ldc.COMPETITION_CODES) if code != "CL"]

    def fake_get(path, params=None):
        if path == "/matches":
            return _ok(in_window)
        return _ok([_match("CL", 99, "2027-02-01T20:00:00Z")])

    res, calls = _upcoming(fake_get)
    assert [path for path, _ in calls] == ["/matches", "/competitions/CL/matches"]
    assert any(f["seasonId"] == "CL" for f in res["data"])


def test_per_competition_limit_still_applies():
    matches = [_match("PL", i, f"2026-03-{i + 1:02d}T12:00:00Z") for i in range(20)]
    matches += [_match(code, 100 + i) for i, code in enumerate(ldc.COMPETITION_CODES) if code != "PL"]
    res, _ = _upcoming(lambda path, params: _ok(matches))
    assert sum(f["seasonId"] == "PL" for f in res["data"]) == ldc.PER_COMPETITION_LIMIT


def test_failed_combined_call_falls_back_to_each_league():
    def fake_get(path, params=None):
        if path == "/matches":
            return {"status": "error", "message": "HTTP 500"}
        return _ok([_match(path.split("/")[2], hash(path) % 1000)])

    res, calls = _upcoming(fake_get)
    assert len(calls) == 1 + len(ldc.COMPETITION_CODES)
    assert res["status"] == "success"
    assert len(res["data"]) == len(ldc.COMPETITION_CODES)


def test_rate_limit_stops_further_calls():
    res, calls = _upcoming(lambda path, params: {"status": "throttled", "code": 429, "message": "429"})
    assert len(calls) == 1
    assert res["status"] == "error"


def test_finished_match_from_today_is_kept_but_older_ones_are_dropped():
    today = date.today()
    old = _match("PL", 1, f"{today - timedelta(days=1)}T12:00:00Z", "FINISHED")
    fresh = _match("BL1", 2, f"{today}T12:00:00Z", "FINISHED")
    rest = [_match(code, 10 + i) for i, code in enumerate(ldc.COMPETITION_CODES)]
    res, _ = _upcoming(lambda path, params: _ok([old, fresh, *rest]))
    ids = {f["id"] for f in res["data"]}
    assert "2" in ids and "1" not in ids


def test_get_upcoming_fixtures_no_key_errors():
    with patch.object(ldc._fdorg, "has_api_key", return_value=False):
        res = ldc.get_upcoming_fixtures()
    assert res["status"] == "error"


# ── Graceful behaviour the engine relies on ───────────────────────────────────

def test_head_to_head_never_errors():
    res = ldc.get_head_to_head(1, 2)
    assert res["status"] == "success"
    assert res["data"] == []


def test_xg_and_lineup_stubs():
    xg = ldc.get_fixture_with_xg(1)
    assert xg["status"] == "success" and xg["data"]["xg"] is None
    lu = ldc.get_fixture_lineups(1, 2, 3)
    assert lu["status"] == "success" and lu["data"]["confirmed"] is False
