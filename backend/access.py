"""Access control for the expensive (Gemini-backed) endpoints.

Four gates, all configured by environment variables so a public deployment can
be handed out as a link without the LLM quota being burned:

1. VERIFIED EMAIL — the Firebase token's `email_verified` claim must be true.
   Google sign-in already counts; email/password accounts must confirm the link.

2. OWNER — `OWNER_EMAILS` is a comma-separated list of exact emails that skip the
   allowlist and both caps. The email must also be verified, otherwise anyone
   could register the owner's address with a password and inherit the bypass.

3. ALLOWLIST — `ALLOWED_EMAILS` is a comma-separated list of the Firebase
   accounts permitted to generate predictions. Unset (the default) means any
   verified account is allowed. Entries are matched case-insensitively; a
   `*@domain.com` entry allows a whole domain.

4. QUOTA — a per-user daily cap (`PREDICTIONS_PER_USER_PER_DAY`) and a global
   daily cap (`PREDICTIONS_PER_DAY_TOTAL`). Counts live in Firestore, updated in
   a transaction, so they survive restarts and a sleeping free-tier instance.
   Days are UTC. A cap of 0 blocks everyone. If Firestore cannot be reached the
   gate fails closed: no count, no prediction.

All gates run only on endpoints that actually call Gemini. Reading fixtures,
standings and analytics stays free and unmetered.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from fastapi import HTTPException, status
from firebase_admin import firestore

from backend.firebase_config import firestore_client

# Sentinel used when a Firebase account somehow has no email claim.
_ANON = "unknown"

DEFAULT_PER_USER_PER_DAY = 3
DEFAULT_TOTAL_PER_DAY = 50

# prediction_quota_days/{YYYY-MM-DD}             {total, users}
# prediction_quota_days/{YYYY-MM-DD}/users/{key} {count}
# Keying by day is what rolls the counts over: a new day is simply a new document.
_DAYS_COLLECTION = "prediction_quota_days"
_USERS_COLLECTION = "users"

_FIRESTORE_TIMEOUT_SECONDS = 10
# /health is public; caching keeps it from spending Firestore's daily free reads.
_SNAPSHOT_TTL_SECONDS = 60


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _email_set(env_name: str) -> set[str]:
    raw = os.getenv(env_name, "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def allowed_emails() -> set[str]:
    """The configured allowlist, lowercased. Empty set = everyone signed in."""
    return _email_set("ALLOWED_EMAILS")


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


def is_email_verified(user: dict) -> bool:
    """True only for the boolean claim: anything else from a token is not verified."""
    return user.get("email_verified") is True


def is_owner(user: dict) -> bool:
    """True when the token's verified email is listed in OWNER_EMAILS (exact match)."""
    email = user.get("email")
    if not email or not is_email_verified(user):
        return False
    return email.lower() in _email_set("OWNER_EMAILS")


@dataclass(frozen=True)
class QuotaReceipt:
    """Proof of one consumed unit. `day` is None when nothing was counted (owner)."""
    key: str
    day: str | None


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _run_in_transaction(client, work: Callable):
    """Run work(transaction), which Firestore retries if the documents change."""
    return firestore.transactional(work)(client.transaction())


def _count(snapshot, field: str) -> int:
    return (snapshot.to_dict() or {}).get(field, 0) if snapshot.exists else 0


class DailyQuota:
    """Per-user and global daily counters, stored in Firestore."""

    def __init__(
        self,
        client: Callable = firestore_client,
        today: Callable[[], str] = _utc_day,
    ) -> None:
        self._client = client
        self._today = today
        self._snapshot_lock = threading.Lock()
        self._snapshot: dict | None = None
        self._snapshot_at = 0.0

    @staticmethod
    def limits() -> tuple[int, int]:
        """(per-user cap, global cap) currently in force."""
        return (
            _env_int("PREDICTIONS_PER_USER_PER_DAY", DEFAULT_PER_USER_PER_DAY),
            _env_int("PREDICTIONS_PER_DAY_TOTAL", DEFAULT_TOTAL_PER_DAY),
        )

    def _refs(self, client, day: str, key: str) -> tuple:
        day_ref = client.collection(_DAYS_COLLECTION).document(day)
        return day_ref, day_ref.collection(_USERS_COLLECTION).document(key)

    def check_and_consume(self, key: str) -> tuple[QuotaReceipt | None, str]:
        """Consume one unit for `key`.

        Returns (receipt, "") or (None, message-if-denied). Raises if Firestore
        fails, so the caller can refuse the prediction rather than run uncounted.
        """
        per_user, total_cap = self.limits()
        client = self._client()
        day = self._today()
        day_ref, user_ref = self._refs(client, day, key)

        # Firestore may re-run this on contention, so it must only touch the transaction.
        def work(transaction) -> str:
            day_doc = day_ref.get(transaction=transaction, timeout=_FIRESTORE_TIMEOUT_SECONDS)
            user_doc = user_ref.get(transaction=transaction, timeout=_FIRESTORE_TIMEOUT_SECONDS)
            total = _count(day_doc, "total")
            used = _count(user_doc, "count")
            if total >= total_cap:
                return (
                    "The app has hit its shared daily prediction limit. "
                    "It resets at 00:00 UTC — please try again tomorrow."
                )
            if used >= per_user:
                return (
                    f"You have used your {per_user} predictions for today. "
                    "The limit resets at 00:00 UTC."
                )
            transaction.set(day_ref, {
                "total": total + 1,
                "users": _count(day_doc, "users") + (0 if user_doc.exists else 1),
            }, merge=True)
            transaction.set(user_ref, {"count": used + 1}, merge=True)
            return ""

        message = _run_in_transaction(client, work)
        if message:
            return None, message
        return QuotaReceipt(key=key, day=day), ""

    def refund(self, receipt: QuotaReceipt) -> None:
        """Give a unit back to the day it was charged, when the prediction failed.

        Never raises: a lost refund costs the user one prediction, whereas raising
        here would hide the failure the caller is already reporting.
        """
        if receipt.day is None:
            return
        try:
            client = self._client()
            day_ref, user_ref = self._refs(client, receipt.day, receipt.key)

            def work(transaction) -> None:
                day_doc = day_ref.get(transaction=transaction, timeout=_FIRESTORE_TIMEOUT_SECONDS)
                user_doc = user_ref.get(transaction=transaction, timeout=_FIRESTORE_TIMEOUT_SECONDS)
                transaction.set(day_ref, {"total": max(0, _count(day_doc, "total") - 1)}, merge=True)
                transaction.set(user_ref, {"count": max(0, _count(user_doc, "count") - 1)}, merge=True)

            _run_in_transaction(client, work)
        except Exception as exc:
            print(f"[Quota] refund failed for day {receipt.day}: {type(exc).__name__}: {exc}")

    def remaining(self, key: str) -> int:
        """Predictions `key` can still make today, counting what's left globally."""
        per_user, total_cap = self.limits()
        client = self._client()
        day_ref, user_ref = self._refs(client, self._today(), key)
        used = _count(user_ref.get(timeout=_FIRESTORE_TIMEOUT_SECONDS), "count")
        total = _count(day_ref.get(timeout=_FIRESTORE_TIMEOUT_SECONDS), "total")
        return max(0, min(per_user - used, total_cap - total))

    def snapshot(self) -> dict:
        """Today's usage for /health. Cached, and never raises."""
        with self._snapshot_lock:
            now = time.monotonic()
            if self._snapshot is None or now - self._snapshot_at >= _SNAPSHOT_TTL_SECONDS:
                self._snapshot = self._read_snapshot()
                self._snapshot_at = now
            return self._snapshot

    def _read_snapshot(self) -> dict:
        per_user, total_cap = self.limits()
        day = self._today()
        used_today = distinct_users = None
        try:
            day_doc = self._client().collection(_DAYS_COLLECTION).document(day).get(
                timeout=_FIRESTORE_TIMEOUT_SECONDS
            )
            used_today = _count(day_doc, "total")
            distinct_users = _count(day_doc, "users")
        except Exception as exc:
            print(f"[Quota] could not read usage: {type(exc).__name__}: {exc}")
        return {
            "day": day,
            "used_today": used_today,
            "daily_total_limit": total_cap,
            "per_user_limit": per_user,
            "distinct_users_today": distinct_users,
        }


quota = DailyQuota()


def user_key(user: dict) -> str:
    return str(user.get("uid") or user.get("email") or _ANON)


def allowance_for(user: dict) -> dict:
    """What `user` may still do today, for display. Raises if Firestore fails."""
    if is_owner(user):
        return {"unlimited": True, "remaining": None, "limit": None}
    per_user, _ = quota.limits()
    return {"unlimited": False, "remaining": quota.remaining(user_key(user)), "limit": per_user}


def enforce(user: dict) -> QuotaReceipt:
    """Verified-email + owner + allowlist + quota gate for one prediction.

    Returns the receipt to pass to `quota.refund` if the prediction then fails.
    Raises 403 for an unverified email or an account off the allowlist, 429 when
    a daily cap is exhausted, and 503 when the counts can't be reached.
    """
    if not is_email_verified(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verify your email to generate predictions. Check your inbox for the link.",
        )
    key = user_key(user)
    if is_owner(user):
        return QuotaReceipt(key=key, day=None)
    if not is_email_allowed(user.get("email")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This account does not have prediction access. "
                "Ask the owner to add your email to the allowlist."
            ),
        )
    try:
        receipt, message = quota.check_and_consume(key)
    except Exception as exc:
        print(f"[Quota] check failed: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Predictions are temporarily unavailable. Please try again in a few minutes.",
        ) from exc
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=message)
    return receipt
