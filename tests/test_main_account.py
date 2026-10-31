"""Tests for DELETE /api/me in backend/main.py.

Deletion is irreversible, so these pin down when it may run and the order of its
two steps. The Firebase and Firestore calls are stubbed; no network is used.
"""
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import main

USER = {"uid": "u1", "email": "someone@example.com", "auth_time": 1}


class Recorder:
    """Records deletion steps in order, failing whichever step it's told to."""

    def __init__(self, fail_on=None):
        self.steps = []
        self.fail_on = fail_on

    def _step(self, name):
        self.steps.append(name)
        if name == self.fail_on:
            raise RuntimeError(f"{name} failed")

    def delete_user_counts(self, key):
        self._step(f"counts:{key}")

    def delete_firebase_user(self, uid):
        self._step(f"account:{uid}")


def _wire(monkeypatch, recorder, recent=True):
    monkeypatch.setattr(main, "quota", recorder)
    monkeypatch.setattr(main, "delete_firebase_user", recorder.delete_firebase_user)
    monkeypatch.setattr(main, "is_recent_sign_in", lambda user: recent)


def test_recent_sign_in_deletes_counts_then_account(monkeypatch):
    recorder = Recorder()
    _wire(monkeypatch, recorder)

    assert main.delete_account(USER) == {"status": "success"}

    assert recorder.steps == ["counts:u1", "account:u1"]


def test_stale_sign_in_gets_428_and_deletes_nothing(monkeypatch):
    recorder = Recorder()
    _wire(monkeypatch, recorder, recent=False)

    with pytest.raises(HTTPException) as exc:
        main.delete_account(USER)

    assert exc.value.status_code == 428
    assert recorder.steps == []


def test_counts_failure_keeps_the_account_so_the_user_can_retry(monkeypatch, capsys):
    recorder = Recorder(fail_on="counts:u1")
    _wire(monkeypatch, recorder)

    with pytest.raises(HTTPException) as exc:
        main.delete_account(USER)

    assert exc.value.status_code == 503
    assert "account:u1" not in recorder.steps
    assert "RuntimeError: counts:u1 failed" in capsys.readouterr().out


def test_account_failure_reports_503(monkeypatch):
    recorder = Recorder(fail_on="account:u1")
    _wire(monkeypatch, recorder)

    with pytest.raises(HTTPException) as exc:
        main.delete_account(USER)

    assert exc.value.status_code == 503


def test_deleting_twice_is_safe_on_retry(monkeypatch):
    # A retry after a partial failure repeats the counts step; that must not fail.
    recorder = Recorder()
    _wire(monkeypatch, recorder)
    main.delete_account(USER)
    main.delete_account(USER)
    assert recorder.steps.count("counts:u1") == 2
