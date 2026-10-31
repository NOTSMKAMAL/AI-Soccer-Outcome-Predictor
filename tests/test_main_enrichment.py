"""Tests for the enrichment layer in backend/main.py.

The prediction page requests a prediction and its enrichment at the same time.
These pin down the fixes for what that caused under the football-data.org rate
limit: duplicate gathers, sections dropped without a trace, and partial data
cached as if it were complete.
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import main

FIXTURE = {"homeTeam": {"id": 533}, "awayTeam": {"id": 524}, "seasonId": "FL1"}
RATE_LIMITED = {"status": "error", "code": 429, "message": "Rate limit: budget exhausted, 29s until reset"}


@pytest.fixture(autouse=True)
def _clean_caches():
    main._enriched_cache.clear()
    main._enrich_in_flight.clear()
    yield
    main._enriched_cache.clear()
    main._enrich_in_flight.clear()


class CountingGather:
    """Stands in for _gather_enriched: counts calls and yields once so callers overlap."""

    def __init__(self, missing_sections=()):
        self.calls = 0
        self.missing_sections = list(missing_sections)

    async def __call__(self, *args):
        self.calls += 1
        await asyncio.sleep(0.01)
        return {"standings": [], "missing_sections": self.missing_sections}


def _run_both(match_id="559644"):
    """Run two enrichments for one match concurrently, as the page's two requests do."""
    async def both():
        return await asyncio.gather(
            main._shared_enrichment(match_id, FIXTURE, 559644),
            main._shared_enrichment(match_id, FIXTURE, 559644),
        )
    return asyncio.run(both())


# ── One gather per match ──────────────────────────────────────────────────────

def test_concurrent_requests_share_one_gather(monkeypatch):
    gather = CountingGather()
    monkeypatch.setattr(main, "_gather_enriched", gather)

    first, second = _run_both()

    assert gather.calls == 1
    assert first is second


def test_different_matches_gather_separately(monkeypatch):
    gather = CountingGather()
    monkeypatch.setattr(main, "_gather_enriched", gather)

    async def two_matches():
        await asyncio.gather(
            main._shared_enrichment("1", FIXTURE, 1),
            main._shared_enrichment("2", FIXTURE, 2),
        )
    asyncio.run(two_matches())

    assert gather.calls == 2


def test_in_flight_entry_is_cleared_after_gather(monkeypatch):
    monkeypatch.setattr(main, "_gather_enriched", CountingGather())
    _run_both()
    assert main._enrich_in_flight == {}


def test_failed_gather_is_cleared_so_next_request_retries(monkeypatch):
    async def broken(*args):
        raise RuntimeError("network down")
    monkeypatch.setattr(main, "_gather_enriched", broken)

    with pytest.raises(RuntimeError):
        asyncio.run(main._shared_enrichment("559644", FIXTURE, 559644))
    assert main._enrich_in_flight == {}


# ── Only complete data is cached ──────────────────────────────────────────────

def test_complete_enrichment_is_cached(monkeypatch):
    monkeypatch.setattr(main, "_gather_enriched", CountingGather())
    _run_both()
    assert "559644" in main._enriched_cache


def test_partial_enrichment_is_not_cached(monkeypatch):
    monkeypatch.setattr(main, "_gather_enriched", CountingGather(missing_sections=["standings"]))
    first, _ = _run_both()
    assert first["missing_sections"] == ["standings"]
    assert "559644" not in main._enriched_cache


# ── Cached enrichment expires ─────────────────────────────────────────────────

class FakeClock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def time(self):
        return self.now


def _cache_complete_enrichment(monkeypatch, clock):
    monkeypatch.setattr(main, "time", clock)
    monkeypatch.setattr(main, "_gather_enriched", CountingGather())
    _run_both()


def test_cached_enrichment_is_served_while_fresh(monkeypatch):
    clock = FakeClock()
    _cache_complete_enrichment(monkeypatch, clock)
    clock.now += main.ENRICHED_TTL_SECONDS - 1
    assert main._cached_enrichment("559644") is not None


def test_cached_enrichment_expires_at_ttl(monkeypatch):
    clock = FakeClock()
    _cache_complete_enrichment(monkeypatch, clock)
    clock.now += main.ENRICHED_TTL_SECONDS
    assert main._cached_enrichment("559644") is None
    assert "559644" not in main._enriched_cache


def test_missing_match_has_no_cached_enrichment():
    assert main._cached_enrichment("never-fetched") is None


def test_enrichment_ttl_matches_standings():
    from storage.league_data_client import STANDINGS_TTL
    assert main.ENRICHED_TTL_SECONDS == STANDINGS_TTL == 300


# ── Failed sections are reported, not swallowed ───────────────────────────────

def test_report_names_failed_sections_and_logs_why(capsys):
    missing = main._report_failed_sections(559644, {
        "team_a_recent_form": {"status": "success", "data": []},
        "standings": RATE_LIMITED,
        "topscorers_with_names": ConnectionError("reset by peer"),
    })

    assert missing == ["standings", "topscorers_with_names"]
    out = capsys.readouterr().out
    assert "[Enrich] standings unavailable for fixture 559644: Rate limit" in out
    assert "ConnectionError: reset by peer" in out


def test_report_treats_empty_success_as_present(capsys):
    # A team with no finished matches in the window is empty, not missing.
    missing = main._report_failed_sections(1, {"team_a_recent_form": {"status": "success", "data": []}})
    assert missing == []
    assert capsys.readouterr().out == ""


def test_gather_marks_rate_limited_sections_missing(monkeypatch, capsys):
    ok_list = {"status": "success", "data": []}
    monkeypatch.setattr(main, "get_fixtures_between_for_team", lambda team_id, *a: RATE_LIMITED if team_id == 524 else ok_list)
    monkeypatch.setattr(main, "get_season_standings", lambda *a: ok_list)
    monkeypatch.setattr(main, "get_fixture_with_xg", lambda *a: {"status": "success", "data": {}})
    monkeypatch.setattr(main, "get_fixture_lineups", lambda *a: {"status": "success", "data": {}})
    monkeypatch.setattr(main, "get_topscorers_with_names", lambda *a: ok_list)
    monkeypatch.setattr(main, "get_squad", lambda *a: ok_list)

    data = asyncio.run(main._gather_enriched(533, 524, "FL1", 559644))

    assert data["missing_sections"] == ["team_b_recent_form"]
    assert "team_b_recent_form unavailable" in capsys.readouterr().out
