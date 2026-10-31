"""Unit tests for storage/league_data_client.py (football-data.org-backed).

The HTTP layer (storage._fdorg) is mocked so these run offline and assert the
normalized shapes that backend/main.py and engine/prediction_engine.py consume.
"""
import os
import sys
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

def test_get_upcoming_fixtures_aggregates_and_sorts():
    def fake_get(path, params=None):
        # one match per competition, with deliberately out-of-order dates
        return {"status": "success", "data": {"matches": [{
            "id": hash(path) % 1000,
            "utcDate": "2026-03-05T12:00:00Z" if "PL" in path else "2026-03-01T12:00:00Z",
            "status": "SCHEDULED",
            "homeTeam": {"id": 1, "name": "H"},
            "awayTeam": {"id": 2, "name": "A"},
            "score": {"fullTime": {"home": None, "away": None}},
        }]}}

    with patch.object(ldc._fdorg, "has_api_key", return_value=True), \
         patch.object(ldc._fdorg, "get", side_effect=fake_get):
        res = ldc.get_upcoming_fixtures()
    assert res["status"] == "success"
    assert res["source"] == "football-data"
    assert len(res["data"]) == len(ldc.COMPETITION_CODES)
    dates = [f["startingAt"] for f in res["data"]]
    assert dates == sorted(dates)                          # sorted ascending


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
