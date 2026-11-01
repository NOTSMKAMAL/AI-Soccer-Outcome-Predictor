"""Tests for how backend/main.py applies the access gate around a prediction.

backend/access.py decides who may predict; these pin down the route's side of the
bargain: nothing reaches Gemini without passing the gate, and a prediction that
fails gives its unit back. The gate and engine are stubbed; no network is used.
"""
import asyncio
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import access, main

USER = {"uid": "u1", "email": "someone@example.com", "email_verified": True}
RECEIPT = access.QuotaReceipt(key="u1", day="2026-10-30")
FIXTURE = {"homeTeam": {"id": 533, "name": "Home"}, "awayTeam": {"id": 524, "name": "Away"}, "_isMock": True}


class RefundLog:
    def __init__(self):
        self.refunded = []

    def refund(self, receipt):
        self.refunded.append(receipt)


class FakeEngine:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = 0

    def __call__(self, *args):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def refunds(monkeypatch):
    log = RefundLog()
    monkeypatch.setattr(main, "quota", log)
    monkeypatch.setattr(main, "enforce_prediction_access", lambda user: RECEIPT)
    monkeypatch.setattr(main, "_engine_available", True)
    monkeypatch.setattr(main, "_tracking_available", False)
    monkeypatch.setattr(main, "_engine_cached_prediction", lambda *args: None, raising=False)
    monkeypatch.setitem(main._fixture_cache, "m1", FIXTURE)
    return log


def _use_engine(monkeypatch, engine):
    monkeypatch.setattr(main, "_engine_generate_prediction", engine, raising=False)


def _predict(match_id="m1"):
    return asyncio.run(main.fixture_prediction(match_id, USER))


def test_successful_prediction_keeps_the_unit(monkeypatch, refunds):
    _use_engine(monkeypatch, FakeEngine(result={"status": "success", "data": {"winner": "Home"}}))
    assert _predict()["data"] == {"winner": "Home"}
    assert refunds.refunded == []


def test_engine_exception_refunds(monkeypatch, refunds):
    _use_engine(monkeypatch, FakeEngine(error=RuntimeError("boom")))
    with pytest.raises(HTTPException) as exc:
        _predict()
    assert exc.value.status_code == 503
    assert refunds.refunded == [RECEIPT]


def test_failed_prediction_refunds(monkeypatch, refunds):
    _use_engine(monkeypatch, FakeEngine(result={"status": "reasoning_failed", "message": "503"}))
    with pytest.raises(HTTPException):
        _predict()
    assert refunds.refunded == [RECEIPT]


def test_gemini_error_text_goes_to_the_log_not_the_user(monkeypatch, refunds, capsys):
    raw = "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'high demand'}}"
    _use_engine(monkeypatch, FakeEngine(result={"status": "reasoning_failed", "message": raw}))

    with pytest.raises(HTTPException) as exc:
        _predict()

    assert exc.value.status_code == 503
    assert "UNAVAILABLE" not in exc.value.detail
    assert "didn't use up a prediction" in exc.value.detail
    assert raw in capsys.readouterr().out


def test_not_enough_data_refunds_and_says_so(monkeypatch, refunds):
    _use_engine(monkeypatch, FakeEngine(result={"status": "insufficient_data"}))
    with pytest.raises(HTTPException) as exc:
        _predict()
    assert exc.value.status_code == 422
    assert "Not enough data for a prediction" in exc.value.detail
    assert refunds.refunded == [RECEIPT]


def test_not_enough_data_is_not_recorded_as_a_prediction(monkeypatch, refunds):
    logged = []
    monkeypatch.setattr(main, "_tracking_available", True)
    monkeypatch.setattr(main, "_tracking", type("Log", (), {"log_prediction": lambda *args: logged.append(args)}), raising=False)
    _use_engine(monkeypatch, FakeEngine(result={"status": "insufficient_data"}))
    with pytest.raises(HTTPException):
        _predict()
    assert logged == []


def test_unknown_fixture_refunds(monkeypatch, refunds):
    engine = FakeEngine()
    _use_engine(monkeypatch, engine)
    with pytest.raises(HTTPException) as exc:
        _predict("not-a-real-fixture")
    assert exc.value.status_code == 404
    assert refunds.refunded == [RECEIPT]
    assert engine.calls == 0


@pytest.mark.parametrize("code", [403, 429, 503])
def test_denied_user_never_reaches_gemini(monkeypatch, refunds, code):
    def deny(user):
        raise HTTPException(status_code=code, detail="denied")
    monkeypatch.setattr(main, "enforce_prediction_access", deny)
    engine = FakeEngine()
    _use_engine(monkeypatch, engine)

    with pytest.raises(HTTPException) as exc:
        _predict()

    assert exc.value.status_code == code
    assert engine.calls == 0
    assert refunds.refunded == []


# ── Cached predictions are free ───────────────────────────────────────────────

CACHED = {"status": "success", "data": {"winner": "Home"}}


def _use_cache(monkeypatch):
    monkeypatch.setattr(main, "_engine_cached_prediction", lambda *args: CACHED, raising=False)


def test_cached_prediction_gives_the_unit_back(monkeypatch, refunds):
    _use_cache(monkeypatch)
    _use_engine(monkeypatch, FakeEngine())
    assert _predict()["data"] == {"winner": "Home"}
    assert refunds.refunded == [RECEIPT]


def test_cached_prediction_never_calls_gemini(monkeypatch, refunds):
    _use_cache(monkeypatch)
    engine = FakeEngine()
    _use_engine(monkeypatch, engine)
    _predict()
    assert engine.calls == 0


def test_cached_prediction_spends_no_football_data_calls(monkeypatch, refunds):
    async def must_not_gather(*args):
        raise AssertionError("a cached prediction must not fetch enrichment")
    _use_cache(monkeypatch)
    _use_engine(monkeypatch, FakeEngine())
    monkeypatch.setattr(main, "_shared_enrichment", must_not_gather)
    monkeypatch.setitem(main._fixture_cache, "12345", {**FIXTURE, "_isMock": False})

    assert _predict("12345")["data"] == {"winner": "Home"}


def test_cached_prediction_is_still_recorded(monkeypatch, refunds):
    # The same pairing can be a different match, whose prediction must be scored too.
    logged = []
    _use_cache(monkeypatch)
    _use_engine(monkeypatch, FakeEngine())
    monkeypatch.setattr(main, "_tracking_available", True)
    monkeypatch.setattr(main, "_tracking", type("T", (), {
        "log_prediction": staticmethod(lambda ctx, home, away, data: logged.append(ctx["match_id"])),
    }), raising=False)

    _predict()

    assert logged == ["m1"]


def test_user_at_cap_is_still_denied_a_cached_prediction(monkeypatch, refunds):
    def deny(user):
        raise HTTPException(status_code=429, detail="spent")
    monkeypatch.setattr(main, "enforce_prediction_access", deny)
    _use_cache(monkeypatch)

    with pytest.raises(HTTPException) as exc:
        _predict()

    assert exc.value.status_code == 429


def test_allowance_endpoint_returns_the_gate_answer(monkeypatch):
    monkeypatch.setattr(main, "allowance_for", lambda user: {"unlimited": False, "remaining": 2, "limit": 3})
    assert main.prediction_allowance(USER)["data"]["remaining"] == 2


def test_allowance_endpoint_reports_503_when_firestore_is_down(monkeypatch, capsys):
    def broken(user):
        raise RuntimeError("firestore down")
    monkeypatch.setattr(main, "allowance_for", broken)

    with pytest.raises(HTTPException) as exc:
        main.prediction_allowance(USER)

    assert exc.value.status_code == 503
    assert "RuntimeError: firestore down" in capsys.readouterr().out
