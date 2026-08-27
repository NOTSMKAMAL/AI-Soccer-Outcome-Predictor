"""Tests for storage/prediction_db.py (SQLite prediction-history store).

Uses a temporary DB file so it never touches the real scripts/data/predictions.db.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage import prediction_db


def setup_function(_fn):
    """Point the store at a fresh temp DB for each test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)  # let sqlite create it fresh
    prediction_db.DB_PATH = path
    prediction_db._initialized = False
    prediction_db.init_db()


def _row(match_id="100", method="dixon-coles", competition="Premier League",
         winner="Arsenal FC", home="Arsenal FC", away="Chelsea FC",
         hp=0.6, dp=0.25, ap=0.15, market=None, edge=None, signal=None):
    return {
        "match_id": match_id, "competition": competition,
        "home_team": home, "away_team": away, "winner": winner,
        "confidence": "medium", "risk_level": "medium",
        "probability_method": method, "match_date": "2026-03-01",
        "home_probability": hp, "draw_probability": dp, "away_probability": ap,
        "market_probability": market, "edge": edge, "signal": signal,
    }


def test_upsert_and_read_roundtrip():
    pid = prediction_db.upsert_prediction(_row())
    assert pid is not None
    rows = prediction_db.read_rows()
    assert len(rows) == 1
    r = rows[0]
    assert r["match_id"] == "100"
    assert r["competition"] == "Premier League"
    assert r["home_probability"] == 0.6
    assert r["result"] is None


def test_upsert_dedupes_on_match_and_method():
    prediction_db.upsert_prediction(_row(hp=0.6))
    prediction_db.upsert_prediction(_row(hp=0.7))   # same match+method → update
    rows = prediction_db.read_rows()
    assert len(rows) == 1
    assert rows[0]["home_probability"] == 0.7


def test_competition_filter():
    prediction_db.upsert_prediction(_row(match_id="1", competition="Premier League"))
    prediction_db.upsert_prediction(_row(match_id="2", competition="WC",
                                         winner="Brazil", home="Brazil", away="Serbia"))
    assert len(prediction_db.read_rows()) == 2
    assert len(prediction_db.read_rows("WC")) == 1
    assert prediction_db.read_rows("WC")[0]["match_id"] == "2"


def test_resolve_outcome_and_correctness():
    prediction_db.upsert_prediction(_row(match_id="5", winner="Arsenal FC"))
    n = prediction_db.resolve_outcomes({"5": {"outcome": "home_win", "final_result": "2-1"}})
    assert n == 1
    r = prediction_db.read_rows()[0]
    assert r["result"] == "home_win"
    assert r["final_result"] == "2-1"
    # resolving again is a no-op (already resolved)
    assert prediction_db.resolve_outcomes({"5": {"outcome": "home_win"}}) == 0


def test_market_snapshots_and_clv():
    prediction_db.upsert_prediction(_row(match_id="9", market=0.50, edge=8.0, signal="Good Value"))
    prediction_db.record_closing_snapshot("9", market_prob=0.58)
    r = prediction_db.read_rows()[0]
    assert r["market_probability"] == 0.50
    assert r["edge"] == 8.0
    assert r["signal"] == "Good Value"
    assert r["closing_market_probability"] == 0.58   # CLV inputs both present


def test_pnl_simulation_on_resolve():
    # Predicted home win, market 0.50 (even money), home actually wins → +1.0 unit.
    prediction_db.upsert_prediction(_row(match_id="11", winner="Arsenal FC", market=0.50))
    prediction_db.resolve_outcomes({"11": {"outcome": "home_win"}})
    conn = prediction_db._connect()
    try:
        pnl = conn.execute("SELECT pnl_simulation FROM outcomes").fetchone()[0]
    finally:
        conn.close()
    assert abs(pnl - 1.0) < 1e-9


def test_no_match_id_is_ignored():
    assert prediction_db.upsert_prediction(_row(match_id="")) is None
    assert prediction_db.read_rows() == []
