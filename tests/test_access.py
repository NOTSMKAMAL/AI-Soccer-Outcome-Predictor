"""Tests for backend/access.py — the allowlist + daily quota gate.

These cover the two ways a public deployment can leak Gemini credit: an account
that should not have access at all, and an account that predicts too often.
"""
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import access


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Every test starts with no allowlist and generous caps unless it sets them."""
    for var in ("ALLOWED_EMAILS", "PREDICTIONS_PER_USER_PER_DAY", "PREDICTIONS_PER_DAY_TOTAL"):
        monkeypatch.delenv(var, raising=False)
    yield


# ── Allowlist ─────────────────────────────────────────────────────────────────

def test_no_allowlist_means_any_signed_in_user(monkeypatch):
    assert access.is_email_allowed("anyone@example.com") is True
    assert access.is_email_allowed(None) is True


def test_allowlist_matches_case_insensitively(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "Owner@Example.com, friend@example.com")
    assert access.is_email_allowed("owner@example.com") is True
    assert access.is_email_allowed("FRIEND@EXAMPLE.COM") is True
    assert access.is_email_allowed("stranger@example.com") is False


def test_allowlist_supports_whole_domain(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "*@ucr.edu")
    assert access.is_email_allowed("student@ucr.edu") is True
    assert access.is_email_allowed("someone@gmail.com") is False


def test_allowlist_rejects_missing_email(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "owner@example.com")
    assert access.is_email_allowed(None) is False


def test_enforce_raises_403_for_blocked_account(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "owner@example.com")
    with pytest.raises(HTTPException) as exc:
        access.enforce({"uid": "u1", "email": "stranger@example.com"})
    assert exc.value.status_code == 403


# ── Daily quota ───────────────────────────────────────────────────────────────

def test_per_user_cap_blocks_the_next_call(monkeypatch):
    monkeypatch.setenv("PREDICTIONS_PER_USER_PER_DAY", "2")
    q = access.DailyQuota()
    assert q.check_and_consume("user-a")[0] is True
    assert q.check_and_consume("user-a")[0] is True
    allowed, message = q.check_and_consume("user-a")
    assert allowed is False
    assert "2 predictions" in message


def test_per_user_cap_is_per_user(monkeypatch):
    monkeypatch.setenv("PREDICTIONS_PER_USER_PER_DAY", "1")
    q = access.DailyQuota()
    assert q.check_and_consume("user-a")[0] is True
    assert q.check_and_consume("user-a")[0] is False
    assert q.check_and_consume("user-b")[0] is True


def test_global_cap_blocks_everyone(monkeypatch):
    monkeypatch.setenv("PREDICTIONS_PER_USER_PER_DAY", "10")
    monkeypatch.setenv("PREDICTIONS_PER_DAY_TOTAL", "2")
    q = access.DailyQuota()
    assert q.check_and_consume("user-a")[0] is True
    assert q.check_and_consume("user-b")[0] is True
    allowed, message = q.check_and_consume("user-c")
    assert allowed is False
    assert "shared daily prediction limit" in message


def test_refund_returns_the_unit(monkeypatch):
    monkeypatch.setenv("PREDICTIONS_PER_USER_PER_DAY", "1")
    q = access.DailyQuota()
    assert q.check_and_consume("user-a")[0] is True
    q.refund("user-a")
    assert q.check_and_consume("user-a")[0] is True


def test_counters_reset_on_a_new_day(monkeypatch):
    monkeypatch.setenv("PREDICTIONS_PER_USER_PER_DAY", "1")
    q = access.DailyQuota()
    assert q.check_and_consume("user-a")[0] is True
    q._day = "1999-01-01"  # simulate crossing UTC midnight
    assert q.check_and_consume("user-a")[0] is True


def test_enforce_raises_429_when_quota_is_spent(monkeypatch):
    monkeypatch.setenv("PREDICTIONS_PER_USER_PER_DAY", "1")
    monkeypatch.setattr(access, "quota", access.DailyQuota())
    user = {"uid": "u1", "email": "owner@example.com"}
    assert access.enforce(user) == "u1"
    with pytest.raises(HTTPException) as exc:
        access.enforce(user)
    assert exc.value.status_code == 429


def test_snapshot_reports_usage(monkeypatch):
    monkeypatch.setenv("PREDICTIONS_PER_DAY_TOTAL", "50")
    q = access.DailyQuota()
    q.check_and_consume("user-a")
    snap = q.snapshot()
    assert snap["used_today"] == 1
    assert snap["daily_total_limit"] == 50
    assert snap["distinct_users_today"] == 1
