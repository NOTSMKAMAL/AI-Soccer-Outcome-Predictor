"""Tests for backend/access.py — the gate in front of Gemini spend.

These cover the ways a public deployment can leak Gemini credit: an unverified
or disallowed account, an account that predicts too often, a counter that resets
when the host sleeps, and a storage outage that must fail closed. Firestore is
replaced by an in-memory fake; nothing here touches the network.
"""
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import access

OWNER = {"uid": "owner-uid", "email": "owner@example.com", "email_verified": True}
PUBLIC = {"uid": "u1", "email": "someone@example.com", "email_verified": True}
SECRET = "test-gate-secret"


class FakeSnapshot:
    def __init__(self, data, reference=None):
        self.exists = data is not None
        self._data = data or {}
        self.reference = reference

    def to_dict(self):
        return dict(self._data)


class FakeDocument:
    def __init__(self, db, path):
        self._db = db
        self.path = path

    def collection(self, name):
        return FakeCollection(self._db, f"{self.path}/{name}")

    def get(self, transaction=None, timeout=None):
        self._db.reads += 1
        return FakeSnapshot(self._db.docs.get(self.path))


class FakeCollection:
    def __init__(self, db, path):
        self._db = db
        self._path = path

    def document(self, doc_id):
        return FakeDocument(self._db, f"{self._path}/{doc_id}")

    def stream(self, timeout=None):
        depth = self._path.count("/") + 2
        for path, data in list(self._db.docs.items()):
            if path.startswith(f"{self._path}/") and path.count("/") + 1 == depth:
                yield FakeSnapshot(data, FakeDocument(self._db, path))


class FakeBatch:
    def __init__(self, db):
        self._db = db
        self._paths = []

    def delete(self, ref):
        self._paths.append(ref.path)

    def commit(self):
        self._db.batch_sizes.append(len(self._paths))
        for path in self._paths:
            self._db.docs.pop(path, None)


class FakeTransaction:
    """Buffers writes until commit, as a real Firestore transaction does."""

    def __init__(self, db):
        self._db = db
        self._writes = []

    def set(self, ref, data, merge=False):
        self._writes.append((ref.path, data))

    def commit(self):
        for path, data in self._writes:
            self._db.docs.setdefault(path, {}).update(data)


class FakeFirestore:
    def __init__(self):
        self.docs = {}
        self.reads = 0
        self.batch_sizes = []

    def collection(self, name):
        return FakeCollection(self, name)

    def batch(self):
        return FakeBatch(self)


def _fake_run_in_transaction(db, work):
    transaction = FakeTransaction(db)
    result = work(transaction)
    transaction.commit()
    return result


def _make_quota(db, day="2026-10-30"):
    return access.DailyQuota(client=lambda: db, today=lambda: day)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Every test starts with no allowlist, no owners and the default caps."""
    for var in ("ALLOWED_EMAILS", "OWNER_EMAILS", "PREDICTIONS_PER_USER_PER_DAY", "PREDICTIONS_PER_DAY_TOTAL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(access, "_run_in_transaction", _fake_run_in_transaction)
    yield


@pytest.fixture
def db(monkeypatch):
    """A fake Firestore wired in as the module-level quota."""
    fake = FakeFirestore()
    monkeypatch.setattr(access, "quota", _make_quota(fake))
    return fake


def _spend(quota, key, times=1):
    return [quota.check_and_consume(key) for _ in range(times)]


def _allowed(result) -> bool:
    receipt, _message = result
    return receipt is not None


# ── Defaults ──────────────────────────────────────────────────────────────────

def test_default_caps_are_three_per_user_and_fifty_total(db):
    assert access.quota.limits() == (3, 50)


def test_unparsable_cap_falls_back_to_the_default(monkeypatch, db):
    monkeypatch.setenv("PREDICTIONS_PER_USER_PER_DAY", "lots")
    assert access.quota.limits()[0] == 3


# ── Allowlist ─────────────────────────────────────────────────────────────────

def test_no_allowlist_means_any_signed_in_user():
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


def test_enforce_raises_403_for_blocked_account(monkeypatch, db):
    monkeypatch.setenv("ALLOWED_EMAILS", "owner@example.com")
    with pytest.raises(HTTPException) as exc:
        access.enforce({"uid": "u1", "email": "stranger@example.com", "email_verified": True})
    assert exc.value.status_code == 403


# ── Verified email ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("claims", [
    {"uid": "u1", "email": "new@example.com", "email_verified": False},
    {"uid": "u1", "email": "new@example.com"},
    {"uid": "u1", "email": "new@example.com", "email_verified": "true"},
])
def test_enforce_rejects_unverified_email_without_spending(claims, db):
    with pytest.raises(HTTPException) as exc:
        access.enforce(claims)
    assert exc.value.status_code == 403
    assert "Verify your email" in exc.value.detail
    assert db.docs == {}


# ── Owner ─────────────────────────────────────────────────────────────────────

def test_owner_skips_both_caps(monkeypatch, db):
    monkeypatch.setenv("OWNER_EMAILS", "owner@example.com")
    monkeypatch.setenv("PREDICTIONS_PER_USER_PER_DAY", "1")
    monkeypatch.setenv("PREDICTIONS_PER_DAY_TOTAL", "1")

    for _ in range(5):
        access.enforce(OWNER)

    assert db.docs == {}


def test_owner_match_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("OWNER_EMAILS", " Owner@Example.com , other@example.com")
    assert access.is_owner(OWNER) is True


def test_owner_email_unverified_gets_no_skip(monkeypatch, db):
    monkeypatch.setenv("OWNER_EMAILS", "owner@example.com")
    unverified = {**OWNER, "email_verified": False}

    assert access.is_owner(unverified) is False
    with pytest.raises(HTTPException) as exc:
        access.enforce(unverified)
    assert exc.value.status_code == 403


def test_owner_needs_the_claim_to_be_exactly_true(monkeypatch):
    monkeypatch.setenv("OWNER_EMAILS", "owner@example.com")
    assert access.is_owner({**OWNER, "email_verified": "true"}) is False
    assert access.is_owner({"uid": "x", "email": "owner@example.com"}) is False


def test_non_owner_is_not_owner(monkeypatch):
    monkeypatch.setenv("OWNER_EMAILS", "owner@example.com")
    assert access.is_owner(PUBLIC) is False


def test_owner_emails_do_not_support_wildcards(monkeypatch):
    # Unlike ALLOWED_EMAILS: a domain entry here would make a whole domain unlimited.
    monkeypatch.setenv("OWNER_EMAILS", "*@example.com")
    assert access.is_owner(PUBLIC) is False


def test_no_owner_configured_means_no_owner():
    assert access.is_owner(OWNER) is False


def test_owner_passes_a_configured_allowlist(monkeypatch, db):
    monkeypatch.setenv("OWNER_EMAILS", "owner@example.com")
    monkeypatch.setenv("ALLOWED_EMAILS", "friend@example.com")
    access.enforce(OWNER)


def test_owner_works_while_firestore_is_down(monkeypatch):
    def broken():
        raise RuntimeError("firestore down")
    monkeypatch.setattr(access, "quota", access.DailyQuota(client=broken))
    monkeypatch.setenv("OWNER_EMAILS", "owner@example.com")
    access.enforce(OWNER)
    assert access.allowance_for(OWNER) == {"unlimited": True, "remaining": None, "limit": None}


def test_owner_refund_is_a_no_op(monkeypatch, db):
    monkeypatch.setenv("OWNER_EMAILS", "owner@example.com")
    access.quota.refund(access.enforce(OWNER))
    assert db.docs == {}


# ── Daily quota ───────────────────────────────────────────────────────────────

def test_per_user_cap_blocks_the_next_call(monkeypatch):
    monkeypatch.setenv("PREDICTIONS_PER_USER_PER_DAY", "2")
    q = _make_quota(FakeFirestore())
    assert all(_allowed(r) for r in _spend(q, "user-a", 2))
    receipt, message = q.check_and_consume("user-a")
    assert receipt is None
    assert "2 predictions" in message


def test_default_per_user_cap_allows_exactly_three(db):
    results = _spend(access.quota, "user-a", 4)
    assert [_allowed(r) for r in results] == [True, True, True, False]


def test_per_user_cap_is_per_user(monkeypatch):
    monkeypatch.setenv("PREDICTIONS_PER_USER_PER_DAY", "1")
    q = _make_quota(FakeFirestore())
    assert _allowed(q.check_and_consume("user-a"))
    assert not _allowed(q.check_and_consume("user-a"))
    assert _allowed(q.check_and_consume("user-b"))


def test_global_cap_blocks_everyone(monkeypatch):
    monkeypatch.setenv("PREDICTIONS_PER_USER_PER_DAY", "10")
    monkeypatch.setenv("PREDICTIONS_PER_DAY_TOTAL", "2")
    q = _make_quota(FakeFirestore())
    assert _allowed(q.check_and_consume("user-a"))
    assert _allowed(q.check_and_consume("user-b"))
    receipt, message = q.check_and_consume("user-c")
    assert receipt is None
    assert "shared daily prediction limit" in message


@pytest.mark.parametrize("var", ["PREDICTIONS_PER_USER_PER_DAY", "PREDICTIONS_PER_DAY_TOTAL"])
def test_cap_of_zero_blocks_rather_than_unlimits(monkeypatch, var):
    monkeypatch.setenv(var, "0")
    q = _make_quota(FakeFirestore())
    assert not _allowed(q.check_and_consume("user-a"))


def test_denied_call_writes_nothing(monkeypatch):
    monkeypatch.setenv("PREDICTIONS_PER_USER_PER_DAY", "1")
    db = FakeFirestore()
    q = _make_quota(db)
    q.check_and_consume("user-a")
    before = {path: dict(doc) for path, doc in db.docs.items()}
    q.check_and_consume("user-a")
    assert db.docs == before


def test_counts_survive_a_restart(monkeypatch):
    # The reason for Firestore: a new process (Render waking up) sees the same counts.
    monkeypatch.setenv("PREDICTIONS_PER_USER_PER_DAY", "1")
    db = FakeFirestore()
    assert _allowed(_make_quota(db).check_and_consume("user-a"))
    assert not _allowed(_make_quota(db).check_and_consume("user-a"))


def test_refund_returns_the_unit(monkeypatch):
    monkeypatch.setenv("PREDICTIONS_PER_USER_PER_DAY", "1")
    q = _make_quota(FakeFirestore())
    receipt, _ = q.check_and_consume("user-a")
    q.refund(receipt)
    assert _allowed(q.check_and_consume("user-a"))


def test_refund_returns_the_global_unit_too(monkeypatch):
    monkeypatch.setenv("PREDICTIONS_PER_USER_PER_DAY", "5")
    monkeypatch.setenv("PREDICTIONS_PER_DAY_TOTAL", "1")
    q = _make_quota(FakeFirestore())
    receipt, _ = q.check_and_consume("user-a")
    q.refund(receipt)
    assert _allowed(q.check_and_consume("user-b"))


def test_double_refund_never_goes_negative():
    db = FakeFirestore()
    q = _make_quota(db)
    receipt, _ = q.check_and_consume("user-a")
    q.refund(receipt)
    q.refund(receipt)
    assert all(v >= 0 for doc in db.docs.values() for k, v in doc.items() if k != "users")


def test_refund_after_midnight_goes_to_the_day_charged(monkeypatch):
    monkeypatch.setenv("PREDICTIONS_PER_USER_PER_DAY", "1")
    db = FakeFirestore()
    day = {"value": "2026-10-30"}
    q = access.DailyQuota(client=lambda: db, today=lambda: day["value"])
    receipt, _ = q.check_and_consume("user-a")

    day["value"] = "2026-10-31"
    assert _allowed(q.check_and_consume("user-a"))
    q.refund(receipt)

    # Refunding yesterday's unit must not free up today's.
    assert not _allowed(q.check_and_consume("user-a"))


def test_failed_refund_is_logged_not_raised(monkeypatch, capsys):
    q = _make_quota(FakeFirestore())
    receipt, _ = q.check_and_consume("user-a")

    def boom(client, work):
        raise ConnectionError("firestore unreachable")
    monkeypatch.setattr(access, "_run_in_transaction", boom)

    q.refund(receipt)

    assert "ConnectionError: firestore unreachable" in capsys.readouterr().out


def test_counters_reset_on_a_new_day(monkeypatch):
    monkeypatch.setenv("PREDICTIONS_PER_USER_PER_DAY", "1")
    db = FakeFirestore()
    day = {"value": "2026-10-30"}
    q = access.DailyQuota(client=lambda: db, today=lambda: day["value"])
    assert _allowed(q.check_and_consume("user-a"))
    assert not _allowed(q.check_and_consume("user-a"))

    day["value"] = "2026-10-31"

    assert _allowed(q.check_and_consume("user-a"))


def test_enforce_raises_429_when_quota_is_spent(monkeypatch, db):
    monkeypatch.setenv("PREDICTIONS_PER_USER_PER_DAY", "1")
    assert access.enforce(PUBLIC).key == "u1"
    with pytest.raises(HTTPException) as exc:
        access.enforce(PUBLIC)
    assert exc.value.status_code == 429


# ── Firestore outage fails closed ─────────────────────────────────────────────

def test_enforce_raises_503_when_firestore_is_down(monkeypatch, capsys):
    def broken():
        raise RuntimeError("firestore down")
    monkeypatch.setattr(access, "quota", access.DailyQuota(client=broken))

    with pytest.raises(HTTPException) as exc:
        access.enforce(PUBLIC)

    assert exc.value.status_code == 503
    assert "RuntimeError: firestore down" in capsys.readouterr().out


def test_enforce_raises_503_when_transaction_fails(monkeypatch, db):
    def boom(client, work):
        raise ConnectionError("aborted")
    monkeypatch.setattr(access, "_run_in_transaction", boom)

    with pytest.raises(HTTPException) as exc:
        access.enforce(PUBLIC)

    assert exc.value.status_code == 503


# ── Allowance shown to the user ───────────────────────────────────────────────

def test_allowance_for_a_new_user_is_the_full_cap(db):
    assert access.allowance_for(PUBLIC) == {"unlimited": False, "remaining": 3, "limit": 3}


def test_allowance_counts_down_and_stops_at_zero(db):
    for expected in (2, 1, 0):
        access.enforce(PUBLIC)
        assert access.allowance_for(PUBLIC)["remaining"] == expected


def test_allowance_is_limited_by_what_is_left_globally(monkeypatch, db):
    monkeypatch.setenv("PREDICTIONS_PER_DAY_TOTAL", "1")
    access.quota.check_and_consume("someone-else")
    assert access.allowance_for(PUBLIC)["remaining"] == 0


def test_allowance_for_owner_is_unlimited_and_reads_nothing(monkeypatch, db):
    monkeypatch.setenv("OWNER_EMAILS", "owner@example.com")
    assert access.allowance_for(OWNER) == {"unlimited": True, "remaining": None, "limit": None}
    assert db.reads == 0


def test_allowance_for_unverified_owner_is_not_unlimited(monkeypatch, db):
    monkeypatch.setenv("OWNER_EMAILS", "owner@example.com")
    assert access.allowance_for({**OWNER, "email_verified": False})["unlimited"] is False


# ── Account deletion ──────────────────────────────────────────────────────────

def _user_docs(db, key):
    return [path for path in db.docs if path.endswith(f"/users/{key}")]


def test_delete_removes_the_users_counts_on_every_day():
    db = FakeFirestore()
    for day in ("2026-10-29", "2026-10-30", "2026-10-31"):
        _make_quota(db, day).check_and_consume("user-a")

    _make_quota(db).delete_user_counts("user-a")

    assert _user_docs(db, "user-a") == []


def test_delete_leaves_other_users_alone():
    db = FakeFirestore()
    q = _make_quota(db)
    q.check_and_consume("user-a")
    q.check_and_consume("user-b")

    q.delete_user_counts("user-a")

    assert len(_user_docs(db, "user-b")) == 1


def test_delete_keeps_the_anonymous_daily_total():
    # Deleting must not hand back global budget; the total holds no personal data.
    db = FakeFirestore()
    q = _make_quota(db)
    q.check_and_consume("user-a")

    q.delete_user_counts("user-a")

    assert db.docs["prediction_quota_days/2026-10-30"]["total"] == 1


def test_delete_with_no_counts_is_fine():
    _make_quota(FakeFirestore()).delete_user_counts("never-predicted")


def test_delete_commits_in_batches_firestore_accepts(monkeypatch):
    monkeypatch.setattr(access, "_DELETE_BATCH_SIZE", 2)
    db = FakeFirestore()
    for day in ("2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31"):
        _make_quota(db, day).check_and_consume("user-a")

    _make_quota(db).delete_user_counts("user-a")

    assert _user_docs(db, "user-a") == []
    assert db.batch_sizes == [2, 2, 1]


def test_delete_failure_raises_so_the_account_is_kept():
    def broken():
        raise RuntimeError("firestore down")
    with pytest.raises(RuntimeError):
        access.DailyQuota(client=broken).delete_user_counts("user-a")


# ── Recent sign-in ────────────────────────────────────────────────────────────

NOW = 2_000_000_000


def test_sign_in_just_now_is_recent():
    assert access.is_recent_sign_in({"auth_time": NOW - 10}, now=NOW) is True


def test_sign_in_at_the_limit_is_recent():
    assert access.is_recent_sign_in({"auth_time": NOW - access.RECENT_SIGN_IN_SECONDS}, now=NOW) is True


def test_sign_in_past_the_limit_is_not_recent():
    assert access.is_recent_sign_in({"auth_time": NOW - access.RECENT_SIGN_IN_SECONDS - 1}, now=NOW) is False


def test_missing_auth_time_is_not_recent():
    assert access.is_recent_sign_in({}, now=NOW) is False


# ── /health snapshot ──────────────────────────────────────────────────────────

def test_snapshot_reports_usage(monkeypatch):
    monkeypatch.setenv("PREDICTIONS_PER_DAY_TOTAL", "50")
    q = _make_quota(FakeFirestore())
    q.check_and_consume("user-a")
    snap = q.snapshot()
    assert snap["used_today"] == 1
    assert snap["daily_total_limit"] == 50
    assert snap["distinct_users_today"] == 1


def test_snapshot_counts_a_returning_user_once(monkeypatch):
    q = _make_quota(FakeFirestore())
    _spend(q, "user-a", 2)
    assert q.snapshot()["distinct_users_today"] == 1


def test_snapshot_is_cached_so_health_cannot_burn_firestore_reads():
    db = FakeFirestore()
    q = _make_quota(db)
    for _ in range(100):
        q.snapshot()
    assert db.reads == 1


def test_snapshot_survives_a_firestore_outage():
    def broken():
        raise RuntimeError("firestore down")
    snap = access.DailyQuota(client=broken).snapshot()
    assert snap["used_today"] is None
    assert snap["per_user_limit"] == 3


class TestRegionGate:
    """Blocked, allowed and missing-header cases, on a deployed server and in local development."""

    @pytest.fixture
    def deployed(self, monkeypatch):
        monkeypatch.setenv("RENDER", "true")
        monkeypatch.setenv("GEO_GATE_SECRET", SECRET)

    @pytest.fixture
    def local(self, monkeypatch):
        monkeypatch.delenv("RENDER", raising=False)
        monkeypatch.delenv("GEO_GATE_SECRET", raising=False)

    @staticmethod
    def _status(secret, country):
        with pytest.raises(HTTPException) as exc:
            access.enforce_region(secret, country)
        return exc.value.status_code

    @pytest.mark.parametrize("country", [
        "DE", "FR", "IE", "ES",  # EU
        "NO", "IS", "LI",        # rest of the EEA
        "CH", "GB",              # named separately in the terms
        "AX", "RE", "GP",        # EU territories that IP lookups report separately
        "GI", "JE", "GG", "IM",  # close to the UK, blocked to be safe
    ])
    def test_blocked_regions_are_refused(self, deployed, country):
        assert self._status(SECRET, country) == 451

    def test_the_whole_eu_is_covered(self):
        assert len(access._EU_COUNTRIES) == 27
        assert access._EU_COUNTRIES <= access.BLOCKED_COUNTRIES

    @pytest.mark.parametrize("country", ["de", " de ", "Gb"])
    def test_case_and_spaces_cannot_get_past_the_list(self, deployed, country):
        assert self._status(SECRET, country) == 451

    @pytest.mark.parametrize("country", ["US", "CA", "BR", "JP", "AU", "TR", "UA", "RS"])
    def test_allowed_countries_pass(self, deployed, country):
        access.enforce_region(SECRET, country)

    @pytest.mark.parametrize("country", [None, "", "   ", "X", "USA", "12", "U1", "XX,US"])
    def test_a_missing_or_malformed_country_is_refused(self, deployed, country):
        assert self._status(SECRET, country) == 451

    @pytest.mark.parametrize("secret", [None, "", "wrong", SECRET + "x", SECRET[:-1]])
    def test_a_wrong_or_missing_secret_is_refused_even_for_an_allowed_country(self, deployed, secret):
        assert self._status(secret, "US") == 403

    def test_a_spoofed_country_without_the_secret_is_refused(self, deployed):
        assert self._status(None, "US") == 403

    def test_render_without_a_secret_refuses_everything(self, monkeypatch, capsys):
        monkeypatch.setenv("RENDER", "true")
        monkeypatch.delenv("GEO_GATE_SECRET", raising=False)
        assert self._status("anything", "US") == 503
        assert "[Region]" in capsys.readouterr().out

    def test_another_host_turns_the_gate_on_with_the_secret_alone(self, monkeypatch):
        monkeypatch.delenv("RENDER", raising=False)
        monkeypatch.setenv("GEO_GATE_SECRET", SECRET)
        assert self._status(None, "US") == 403

    def test_local_development_is_unaffected(self, local):
        access.enforce_region(None, None)
        access.enforce_region(None, "DE")

    def test_the_message_tells_a_blocked_visitor_what_still_works(self, deployed):
        with pytest.raises(HTTPException) as exc:
            access.enforce_region(SECRET, "DE")
        assert "European Economic Area" in exc.value.detail
        assert "browse fixtures" in exc.value.detail
