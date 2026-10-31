"""Tests for backend/firebase_config.py — Firebase ID token verification.

Every verification failure reaches the client as the same 401, so these pin down
the two things that make that debuggable and safe: the server logs why (type and
message, never the token), and a server clock slightly behind Google's does not
reject freshly issued tokens ("Token used too early").
"""
import os
import sys

import pytest
from firebase_admin.auth import ExpiredIdTokenError, InvalidIdTokenError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import firebase_config

TOKEN = "header.payload.signature-of-a-test-token"


class FakeVerifier:
    """Stands in for firebase_admin.auth.verify_id_token: records kwargs, then returns or raises."""

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def __call__(self, token, **kwargs):
        self.calls.append((token, kwargs))
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def initialized_app(monkeypatch):
    """Pretend Firebase Admin initialized, so verify_id_token reaches the SDK call."""
    monkeypatch.setattr(firebase_config, "_get_app", lambda: object())


def _use_verifier(monkeypatch, verifier):
    monkeypatch.setattr(firebase_config.auth, "verify_id_token", verifier)


# ── Clock skew (the "Token used too early" regression) ───────────────────────

def test_tolerates_server_clock_behind_token_issuer(monkeypatch, initialized_app):
    verifier = FakeVerifier(result={"uid": "u1"})
    _use_verifier(monkeypatch, verifier)

    assert firebase_config.verify_id_token(TOKEN) == {"uid": "u1"}

    _, kwargs = verifier.calls[0]
    # The SDK default of 0 rejected tokens when this machine's clock lagged ~1s.
    assert kwargs["clock_skew_seconds"] >= 1


def test_clock_skew_stays_within_firebase_limit():
    # firebase_admin raises ValueError for values outside 0–60.
    assert 0 < firebase_config.TOKEN_CLOCK_SKEW_SECONDS <= 60


def test_still_checks_revocation(monkeypatch, initialized_app):
    verifier = FakeVerifier(result={"uid": "u1"})
    _use_verifier(monkeypatch, verifier)

    firebase_config.verify_id_token(TOKEN)

    assert verifier.calls[0][1]["check_revoked"] is True


# ── Failures are logged, not swallowed ───────────────────────────────────────

def test_token_error_returns_none_and_logs_type_and_message(monkeypatch, initialized_app, capsys):
    error = InvalidIdTokenError("Token used too early, 1793328399 < 1793328400.")
    _use_verifier(monkeypatch, FakeVerifier(error=error))

    assert firebase_config.verify_id_token(TOKEN) is None

    out = capsys.readouterr().out
    assert "InvalidIdTokenError" in out
    assert "Token used too early" in out


def test_expired_token_is_logged(monkeypatch, initialized_app, capsys):
    _use_verifier(monkeypatch, FakeVerifier(error=ExpiredIdTokenError("Token expired", cause=None)))

    assert firebase_config.verify_id_token(TOKEN) is None
    assert "ExpiredIdTokenError" in capsys.readouterr().out


def test_unexpected_error_returns_none_and_logs_type(monkeypatch, initialized_app, capsys):
    # e.g. the check_revoked network call failing — not the client's fault, but still a 401 today.
    _use_verifier(monkeypatch, FakeVerifier(error=ConnectionError("identitytoolkit unreachable")))

    assert firebase_config.verify_id_token(TOKEN) is None

    out = capsys.readouterr().out
    assert "ConnectionError" in out
    assert "identitytoolkit unreachable" in out


def test_log_never_contains_the_token(monkeypatch, initialized_app, capsys):
    _use_verifier(monkeypatch, FakeVerifier(error=InvalidIdTokenError(f"Bad token: {TOKEN}")))

    firebase_config.verify_id_token(TOKEN)

    out = capsys.readouterr().out
    assert TOKEN not in out
    assert "<token>" in out


# ── Guards before the SDK call ───────────────────────────────────────────────

def test_empty_token_never_reaches_firebase(monkeypatch, initialized_app):
    verifier = FakeVerifier(result={"uid": "u1"})
    _use_verifier(monkeypatch, verifier)

    assert firebase_config.verify_id_token("") is None
    assert verifier.calls == []


def test_uninitialized_app_rejects_without_calling_sdk(monkeypatch):
    monkeypatch.setattr(firebase_config, "_get_app", lambda: None)
    verifier = FakeVerifier(result={"uid": "u1"})
    _use_verifier(monkeypatch, verifier)

    assert firebase_config.verify_id_token(TOKEN) is None
    assert verifier.calls == []
