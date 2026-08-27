"""Access control for the expensive (Gemini-backed) endpoints.

Two independent gates, both configured by environment variables so a public
deployment can be handed out as a link without the LLM quota being burned:

1. ALLOWLIST — `ALLOWED_EMAILS` is a comma-separated list of the Firebase
   accounts permitted to generate predictions. Unset (the default) means any
   signed-in account is allowed, which is what you want in local development.
   Entries are matched case-insensitively; a `*@domain.com` entry allows a whole
   domain.

2. QUOTA — a per-user daily cap (`PREDICTIONS_PER_USER_PER_DAY`) and a global
   daily cap (`PREDICTIONS_PER_DAY_TOTAL`) on prediction generations. Counters
   are in-process and reset at UTC midnight (and on restart), which is the right
   trade-off for a single free-tier instance: no database, no extra dependency,
   and the cap can only ever be *under*-counted after a restart, never bypassed
   while the process is up.

Both gates run only on endpoints that actually call Gemini. Reading fixtures,
standings and analytics stays free and unmetered.
"""
from __future__ import annotations

import os
import threading
from datetime import datetime, timezone

from fastapi import HTTPException, status

# Sentinel used when a Firebase account somehow has no email claim.
_ANON = "unknown"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def allowed_emails() -> set[str]:
    """The configured allowlist, lowercased. Empty set = everyone signed in."""
    raw = os.getenv("ALLOWED_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_email_allowed(email: str | None) -> bool:
    allow = allowed_emails()
    if not allow:
        return True  # no allowlist configured — any signed-in user may predict
    if not email:
        return False
    email = email.lower()
    if email in allow:
        return True
    domain = email.rpartition("@")[2]
    return bool(domain) and f"*@{domain}" in allow


class DailyQuota:
    """Per-user and global daily counters, reset at UTC midnight."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._day = self._today()
        self._per_user: dict[str, int] = {}
        self._total = 0

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _roll(self) -> None:
        today = self._today()
        if today != self._day:
            self._day = today
            self._per_user.clear()
            self._total = 0

    def check_and_consume(self, key: str) -> tuple[bool, str]:
        """Consume one unit for `key`. Returns (allowed, message-if-denied)."""
        per_user = _env_int("PREDICTIONS_PER_USER_PER_DAY", 25)
        total_cap = _env_int("PREDICTIONS_PER_DAY_TOTAL", 200)
        with self._lock:
            self._roll()
            if total_cap > 0 and self._total >= total_cap:
                return False, (
                    "The app has hit its shared daily prediction limit. "
                    "It resets at 00:00 UTC — please try again tomorrow."
                )
            used = self._per_user.get(key, 0)
            if per_user > 0 and used >= per_user:
                return False, (
                    f"You have used your {per_user} predictions for today. "
                    "The limit resets at 00:00 UTC."
                )
            self._per_user[key] = used + 1
            self._total += 1
            return True, ""

    def refund(self, key: str) -> None:
        """Give a unit back when the prediction failed before reaching Gemini."""
        with self._lock:
            self._roll()
            if self._per_user.get(key):
                self._per_user[key] -= 1
            if self._total:
                self._total -= 1

    def snapshot(self) -> dict:
        with self._lock:
            self._roll()
            return {
                "day": self._day,
                "used_today": self._total,
                "daily_total_limit": _env_int("PREDICTIONS_PER_DAY_TOTAL", 200),
                "per_user_limit": _env_int("PREDICTIONS_PER_USER_PER_DAY", 25),
                "distinct_users_today": len(self._per_user),
            }


quota = DailyQuota()


def user_key(user: dict) -> str:
    return str(user.get("uid") or user.get("email") or _ANON)


def enforce(user: dict) -> str:
    """Allowlist + quota gate for one prediction. Returns the quota key.

    Raises 403 when the account is not on the allowlist, or 429 when a daily
    cap is exhausted.
    """
    email = user.get("email")
    if not is_email_allowed(email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This account does not have prediction access. "
                "Ask the owner to add your email to the allowlist."
            ),
        )
    key = user_key(user)
    ok, message = quota.check_and_consume(key)
    if not ok:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=message)
    return key
