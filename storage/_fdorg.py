"""Shared football-data.org v4 HTTP helpers.

storage/league_data_client.py (domestic leagues + Champions League) sits on top
of these, so auth, the request envelope, and the error shapes live in one place.

Free tier: 10 requests/minute. Two mechanisms keep us under it:

1. **Server-reported budget.** Every response carries the requests left before
   being blocked and `X-RequestCounter-Reset` (seconds until the counter resets).
   We record both and refuse to send another request while the budget is
   exhausted — football-data.org explicitly asks clients to throttle on these
   headers rather than discovering the limit by being blocked.

   Note: the docs name the first header `X-RequestsAvailable`, but the live v4 API
   currently sends `x-requests-available-minute`. Both are accepted (see
   `_AVAILABLE_HEADERS`) so this keeps working whichever one arrives.
2. **Local sliding window.** Headers only arrive *after* a response, so several
   concurrent requests could otherwise fire before the first one reports back
   (the enrichment path issues up to 7 at once). When we have no fresh figure from
   the server, a local 60-second window caps what we send. A fresh server figure
   always wins over the local window — its counter is the one that matters — and
   we decrement it optimistically per request so a concurrent burst still counts.

When a wait would exceed `FOOTBALL_DATA_MAX_WAIT` seconds, `get()` returns a
throttled error envelope instead of blocking — every caller already degrades to
its cache or to mock data, which is far better than a hung request.

Tunable via env: FOOTBALL_DATA_MAX_PER_MINUTE (default 10),
FOOTBALL_DATA_MAX_WAIT (default 12 seconds).
"""
import os
import threading
import time
from collections import deque

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.football-data.org/v4"
API_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "")

WINDOW_SECONDS = 60.0

# Header carrying "requests left in this window". The documented name and the one
# the live API actually returns differ, so accept either (first match wins).
_AVAILABLE_HEADERS = ("X-RequestsAvailable", "x-requests-available-minute")
_RESET_HEADER = "X-RequestCounter-Reset"

# ── Throttle state (shared across threads: enrichment calls run concurrently) ──
_lock = threading.Lock()
_recent: deque = deque()          # monotonic timestamps of requests we have sent
_remaining: int | None = None     # X-RequestsAvailable from the newest response
_reset_at: float = 0.0            # monotonic deadline from X-RequestCounter-Reset


def _max_per_minute() -> int:
    try:
        return max(1, int(os.getenv("FOOTBALL_DATA_MAX_PER_MINUTE", "") or 10))
    except ValueError:
        return 10


def _max_wait() -> float:
    try:
        return max(0.0, float(os.getenv("FOOTBALL_DATA_MAX_WAIT", "") or 12))
    except ValueError:
        return 12.0


def has_api_key() -> bool:
    """True when a football-data.org token is configured (env wins over import-time)."""
    return bool(os.getenv("FOOTBALL_DATA_API_KEY", "") or API_KEY)


def headers() -> dict:
    """Auth header, re-reading the env on each call so a late-set key still works."""
    key = os.getenv("FOOTBALL_DATA_API_KEY", "") or API_KEY
    return {"X-Auth-Token": key} if key else {}


# ── Throttling ────────────────────────────────────────────────────────────────

def _wait_needed(now: float) -> float:
    """Seconds to wait before another request may be sent. Caller holds the lock."""
    global _remaining
    while _recent and now - _recent[0] >= WINDOW_SECONDS:
        _recent.popleft()

    if _remaining is not None and now >= _reset_at:
        _remaining = None  # the window it referred to has expired — no longer valid

    if _remaining is not None:
        # The server's own counter is authoritative while it is fresh.
        return 0.0 if _remaining > 0 else _reset_at - now

    # Nothing fresh from the server (first call, missing header, or a burst that
    # has not reported back yet) — fall back to our own window.
    if len(_recent) >= _max_per_minute():
        return WINDOW_SECONDS - (now - _recent[0])
    return 0.0


def _reserve_slot() -> float:
    """Claim a request slot, sleeping if needed.


    Returns 0.0 once a slot is claimed, or the remaining wait (> 0) if that wait
    would exceed FOOTBALL_DATA_MAX_WAIT — in which case no slot is claimed and the
    caller should give up rather than block.
    """
    global _remaining
    deadline = time.monotonic() + _max_wait()
    while True:
        with _lock:
            now = time.monotonic()
            wait = _wait_needed(now)
            if wait <= 0:
                _recent.append(now)
                if _remaining is not None and _remaining > 0:
                    # Spend it now: concurrent requests must not all see the same
                    # figure while their own responses are still in flight.
                    _remaining -= 1
                return 0.0
            if now + wait > deadline:
                return wait
        # Sleep outside the lock so other threads can still read state.
        time.sleep(min(wait, 1.0) + 0.05)


def _note_response(resp: "requests.Response") -> None:
    """Record the throttling headers football-data.org returns on every response."""
    global _remaining, _reset_at

    def _int_header(*names: str) -> int | None:
        for name in names:
            raw = resp.headers.get(name)
            if raw is None:
                continue
            try:
                return int(str(raw).strip())
            except (TypeError, ValueError):
                continue
        return None

    available = _int_header(*_AVAILABLE_HEADERS)
    reset_in = _int_header(_RESET_HEADER)
    with _lock:
        if available is not None:
            _remaining = available
        if reset_in is not None:
            _reset_at = time.monotonic() + max(0, reset_in)


def snapshot() -> dict:
    """Current throttle state — surfaced by /health for debugging."""
    with _lock:
        now = time.monotonic()
        return {
            "requests_available": _remaining,
            "counter_resets_in": max(0, round(_reset_at - now)) if _reset_at > now else 0,
            "sent_last_60s": sum(1 for t in _recent if now - t < WINDOW_SECONDS),
            "max_per_minute": _max_per_minute(),
        }


def reset_state() -> None:
    """Clear throttle state. Test helper — not used in production paths."""
    global _remaining, _reset_at
    with _lock:
        _recent.clear()
        _remaining = None
        _reset_at = 0.0


# ── Request ───────────────────────────────────────────────────────────────────

def get(path: str, params: dict | None = None) -> dict:
    """GET against football-data.org and return a {"status", "data"|"message"} envelope.

    Throttles ahead of the request using the server's own budget headers, and
    retries once on a 429 when the counter resets soon enough to be worth waiting.
    """
    url = f"{BASE_URL}{path}"

    for attempt in (0, 1):
        wait = _reserve_slot()
        if wait > 0:
            return {
                "status": "error",
                "code": 429,
                "message": (
                    f"Rate limit: football-data.org budget exhausted, "
                    f"{round(wait)}s until reset — serving cached/mock data instead."
                ),
            }
        try:
            resp = requests.get(url, headers=headers(), params=params or {}, timeout=10)
            _note_response(resp)
            resp.raise_for_status()
            return {"status": "success", "data": resp.json()}
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code if e.response is not None else None
            if code == 429 and attempt == 0:
                # The response already updated _remaining/_reset_at, so the next
                # _reserve_slot() waits (or bails out) with the server's own timing.
                continue
            return {"status": "error", "message": f"HTTP {code}: {e}", "code": code}
        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": str(e)}

    return {"status": "error", "code": 429, "message": "Rate limited by football-data.org."}
