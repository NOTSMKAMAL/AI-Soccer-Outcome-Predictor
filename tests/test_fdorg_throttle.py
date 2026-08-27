"""Tests for storage/_fdorg.py — football-data.org throttling.

football-data.org asks clients to throttle on the response headers
(`X-RequestsAvailable`, `X-RequestCounter-Reset`) rather than discovering the
limit by getting blocked. These tests run entirely offline: `requests.get` is
replaced with a fake that returns whatever headers the test wants.
"""
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage import _fdorg


class FakeClock:
    """Stand-in for the `time` module: sleeping advances a virtual clock.

    Without this, a test that exercises the wait path would spin for a real
    minute — the production loop re-checks `monotonic()` after every sleep.
    """

    def __init__(self):
        self.now = 1000.0
        self.slept: list[float] = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


class FakeResponse:
    def __init__(self, status_code=200, headers=None, payload=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._payload = payload if payload is not None else {"ok": True}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.exceptions.HTTPError(f"{self.status_code} error", response=self)


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    """Each test starts with empty throttle state and default limits."""
    monkeypatch.setenv("FOOTBALL_DATA_API_KEY", "test-key")
    monkeypatch.delenv("FOOTBALL_DATA_MAX_PER_MINUTE", raising=False)
    monkeypatch.delenv("FOOTBALL_DATA_MAX_WAIT", raising=False)
    _fdorg.reset_state()
    yield
    _fdorg.reset_state()


# ── Header parsing ────────────────────────────────────────────────────────────

def test_records_budget_headers_from_a_response():
    resp = FakeResponse(headers={"X-RequestsAvailable": "7", "X-RequestCounter-Reset": "23"})
    with patch("storage._fdorg.requests.get", return_value=resp):
        assert _fdorg.get("/competitions/PL/matches")["status"] == "success"
    snap = _fdorg.snapshot()
    assert snap["requests_available"] == 7
    assert 0 < snap["counter_resets_in"] <= 23
    assert snap["sent_last_60s"] == 1


def test_reads_the_header_name_the_live_api_actually_sends():
    """The live v4 API sends `x-requests-available-minute`, not the documented name."""
    resp = FakeResponse(headers={"x-requests-available-minute": "8", "X-RequestCounter-Reset": "52"})
    with patch("storage._fdorg.requests.get", return_value=resp):
        assert _fdorg.get("/competitions/PD/standings")["status"] == "success"
    assert _fdorg.snapshot()["requests_available"] == 8


def test_missing_or_malformed_headers_are_ignored():
    resp = FakeResponse(headers={"X-RequestsAvailable": "not-a-number",
                                 "x-requests-available-minute": "also-bad"})
    with patch("storage._fdorg.requests.get", return_value=resp):
        assert _fdorg.get("/competitions/PL/matches")["status"] == "success"
    assert _fdorg.snapshot()["requests_available"] is None


def test_fresh_server_budget_overrides_a_full_local_window(monkeypatch):
    """The server's counter wins: a full local window must not block real budget."""
    monkeypatch.setenv("FOOTBALL_DATA_MAX_PER_MINUTE", "3")
    monkeypatch.setenv("FOOTBALL_DATA_MAX_WAIT", "0")
    ok = FakeResponse(headers={"x-requests-available-minute": "9", "X-RequestCounter-Reset": "58"})
    with patch("storage._fdorg.requests.get", return_value=ok) as mock_get:
        results = [_fdorg.get(f"/p{i}") for i in range(5)]
        assert mock_get.call_count == 5
    assert all(r["status"] == "success" for r in results)


def test_stale_server_budget_is_discarded(monkeypatch):
    """Once the reset window passes, an old '0 available' must not block forever."""
    monkeypatch.setenv("FOOTBALL_DATA_MAX_WAIT", "0")
    clock = FakeClock()
    monkeypatch.setattr(_fdorg, "time", clock)
    _fdorg.reset_state()

    spent = FakeResponse(headers={"x-requests-available-minute": "0", "X-RequestCounter-Reset": "30"})
    with patch("storage._fdorg.requests.get", return_value=spent) as mock_get:
        _fdorg.get("/first")
        assert _fdorg.get("/blocked")["status"] == "error"
        assert mock_get.call_count == 1
        clock.now += 31  # the counter window has now elapsed
        assert _fdorg.get("/after-reset")["status"] == "success"
        assert mock_get.call_count == 2


def test_a_burst_decrements_the_budget_before_responses_land(monkeypatch):
    """Concurrent calls must not all read the same 'available' figure."""
    monkeypatch.setenv("FOOTBALL_DATA_MAX_WAIT", "0")
    # Every response reports 2 available; without optimistic decrementing this
    # would let an unlimited burst through.
    stale = FakeResponse(headers={"x-requests-available-minute": "2", "X-RequestCounter-Reset": "50"})
    with patch("storage._fdorg.requests.get", return_value=stale) as mock_get:
        statuses = [_fdorg.get(f"/b{i}")["status"] for i in range(6)]
        assert mock_get.call_count == 6, "each response refreshes the figure to 2"
    assert statuses == ["success"] * 6


# ── Throttling behaviour ──────────────────────────────────────────────────────

def test_exhausted_budget_short_circuits_instead_of_calling(monkeypatch):
    """With 0 requests available, the next call must not hit the network."""
    monkeypatch.setenv("FOOTBALL_DATA_MAX_WAIT", "0")
    spent = FakeResponse(headers={"X-RequestsAvailable": "0", "X-RequestCounter-Reset": "45"})
    with patch("storage._fdorg.requests.get", return_value=spent) as mock_get:
        _fdorg.get("/first")
        assert mock_get.call_count == 1
        result = _fdorg.get("/second")
        assert mock_get.call_count == 1, "must not send a request while blocked"
    assert result["status"] == "error"
    assert result["code"] == 429
    assert "Rate limit" in result["message"]


def test_local_window_caps_requests_before_headers_arrive(monkeypatch):
    """Concurrent calls are capped even if the server has not reported a budget."""
    monkeypatch.setenv("FOOTBALL_DATA_MAX_PER_MINUTE", "3")
    monkeypatch.setenv("FOOTBALL_DATA_MAX_WAIT", "0")
    bare = FakeResponse()  # no throttling headers at all
    with patch("storage._fdorg.requests.get", return_value=bare) as mock_get:
        results = [_fdorg.get(f"/p{i}") for i in range(5)]
        assert mock_get.call_count == 3
    assert [r["status"] for r in results] == ["success"] * 3 + ["error"] * 2
    assert all(r["code"] == 429 for r in results[3:])


def test_waits_when_the_reset_is_within_the_allowed_wait(monkeypatch):
    """A short reset window is waited out rather than failed."""
    monkeypatch.setenv("FOOTBALL_DATA_MAX_PER_MINUTE", "1")
    monkeypatch.setenv("FOOTBALL_DATA_MAX_WAIT", "90")
    clock = FakeClock()
    monkeypatch.setattr(_fdorg, "time", clock)
    _fdorg.reset_state()

    bare = FakeResponse()
    with patch("storage._fdorg.requests.get", return_value=bare) as mock_get:
        assert _fdorg.get("/one")["status"] == "success"
        assert _fdorg.get("/two")["status"] == "success"
        assert mock_get.call_count == 2
    assert clock.slept, "should have slept rather than giving up"
    assert sum(clock.slept) >= 60, "should wait out the full 60s window"


def test_429_is_retried_once_after_the_counter_resets(monkeypatch):
    monkeypatch.setenv("FOOTBALL_DATA_MAX_WAIT", "90")
    clock = FakeClock()
    monkeypatch.setattr(_fdorg, "time", clock)
    _fdorg.reset_state()

    blocked = FakeResponse(
        status_code=429,
        headers={"X-RequestsAvailable": "0", "X-RequestCounter-Reset": "2"},
    )
    ok = FakeResponse(headers={"X-RequestsAvailable": "9", "X-RequestCounter-Reset": "58"})
    with patch("storage._fdorg.requests.get", side_effect=[blocked, ok]) as mock_get:
        result = _fdorg.get("/competitions/PL/standings")
        assert mock_get.call_count == 2
    assert result["status"] == "success"
    assert clock.slept, "should have waited for the counter to reset"


def test_429_gives_up_when_the_reset_is_too_far_away(monkeypatch):
    monkeypatch.setenv("FOOTBALL_DATA_MAX_WAIT", "0")
    blocked = FakeResponse(
        status_code=429,
        headers={"X-RequestsAvailable": "0", "X-RequestCounter-Reset": "55"},
    )
    with patch("storage._fdorg.requests.get", return_value=blocked) as mock_get:
        result = _fdorg.get("/competitions/PL/standings")
        assert mock_get.call_count == 1
    assert result["status"] == "error"
    assert result["code"] == 429


def test_other_http_errors_are_not_retried(monkeypatch):
    forbidden = FakeResponse(status_code=403)
    with patch("storage._fdorg.requests.get", return_value=forbidden) as mock_get:
        result = _fdorg.get("/competitions/PL/matches")
        assert mock_get.call_count == 1
    assert result["status"] == "error"
    assert result["code"] == 403


def test_network_error_returns_an_error_envelope():
    import requests
    with patch("storage._fdorg.requests.get", side_effect=requests.exceptions.ConnectionError("boom")):
        result = _fdorg.get("/competitions/PL/matches")
    assert result["status"] == "error"
    assert "boom" in result["message"]
