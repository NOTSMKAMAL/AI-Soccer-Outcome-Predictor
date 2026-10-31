import asyncio
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from backend.access import enforce as enforce_prediction_access, quota
from backend.firebase_config import verify_id_token
from storage import _fdorg
from storage.league_data_client import (
    STANDINGS_TTL,
    get_upcoming_fixtures,
    get_fixture_detail,
    get_fixtures_between_for_team,
    get_season_standings,
    get_fixture_with_xg,
    get_fixture_lineups,
    get_topscorers_with_names,
    get_squad,
)

# Lazy import — engine needs GEMINI_API_KEY; catch missing-key errors at call time
try:
    from engine.prediction_engine import generate_prediction as _engine_generate_prediction
    _engine_available = True
except Exception:
    _engine_available = False

try:
    from engine import tracking as _tracking
    _tracking_available = True
except Exception:
    _tracking_available = False


app = FastAPI(title="AI Sports Outcome Predictor", version="1.0.0")

# Browser origins allowed to call this API. Set ALLOWED_ORIGINS (comma-separated)
# to your deployed frontend URL; unset means "any origin", which is fine locally
# because every expensive endpoint additionally requires a Firebase ID token.
_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory caches ──────────────────────────────────────────────────────────
_fixture_cache: dict[str, dict] = {}
# Complete enrichment by match id: {"data", "ts"}. Expires with the standings it
# is built from, so form and the table can't go stale on a long-running server.
_enriched_cache: dict[str, dict] = {}
ENRICHED_TTL_SECONDS = STANDINGS_TTL
# Enrichment gathers currently running, by match id. The prediction page fires
# POST /prediction and GET /enriched together; without this both would gather
# the same data, doubling football-data.org calls against a 10/min budget.
_enrich_in_flight: dict[str, asyncio.Task] = {}

# Server-side TTL cache for the full fixture list.
# Distinct from _fixture_cache (per-ID dict used for individual lookups).
_fixtures_ttl: dict = {}        # keys: "data", "source", "ts"
FIXTURES_TTL_SECONDS = 300      # 5 minutes — resets on server restart

# Demo fixtures used only when football-data.org returns nothing (no API key, or
# every competition errored). The page still loads and is clearly flagged as
# preview data. These IDs are NOT real football-data.org IDs, so prediction
# fails gracefully for them by design.
MOCK_FIXTURES: list[dict] = [
    {
        "id": "mock-pl-1",
        "name": "Arsenal FC vs Chelsea FC",
        "homeTeam": {"id": 57, "name": "Arsenal FC"},
        "awayTeam": {"id": 61, "name": "Chelsea FC"},
        "startingAt": "2026-01-01 17:00:00",
        "leagueId": 2021,
        "leagueName": "Premier League",
        "status": "upcoming",
        "_isMock": True,
    },
    {
        "id": "mock-pl-2",
        "name": "Liverpool FC vs Manchester City FC",
        "homeTeam": {"id": 64, "name": "Liverpool FC"},
        "awayTeam": {"id": 65, "name": "Manchester City FC"},
        "startingAt": "2026-01-01 20:00:00",
        "leagueId": 2021,
        "leagueName": "Premier League",
        "status": "upcoming",
        "_isMock": True,
    },
    {
        "id": "mock-pd-1",
        "name": "Real Madrid CF vs FC Barcelona",
        "homeTeam": {"id": 86, "name": "Real Madrid CF"},
        "awayTeam": {"id": 81, "name": "FC Barcelona"},
        "startingAt": "2026-01-02 20:00:00",
        "leagueId": 2014,
        "leagueName": "La Liga",
        "status": "upcoming",
        "_isMock": True,
    },
    {
        "id": "mock-sa-1",
        "name": "FC Internazionale Milano vs AC Milan",
        "homeTeam": {"id": 108, "name": "FC Internazionale Milano"},
        "awayTeam": {"id": 98, "name": "AC Milan"},
        "startingAt": "2026-01-02 19:00:00",
        "leagueId": 2019,
        "leagueName": "Serie A",
        "status": "upcoming",
        "_isMock": True,
    },
]

LA_TZ = ZoneInfo("America/Los_Angeles")

def _mock_fixture_at(offset_days: int, la_hour: int) -> str:
    """Return a UTC kickoff string whose calendar day is based on Los Angeles."""
    now_la = datetime.now(LA_TZ)
    kickoff_la = (
        now_la.replace(hour=la_hour, minute=0, second=0, microsecond=0)
        + timedelta(days=offset_days)
    )
    return kickoff_la.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _get_mock_fixtures() -> list[dict]:
    """Demo fixtures with kickoff times pinned to today/tomorrow in LA time."""
    fixtures = [dict(f) for f in MOCK_FIXTURES]
    fixtures[0].update({
        "id": "mock-pl-today-1",
        "startingAt": _mock_fixture_at(0, 9),
        "status": "finished",
        "score": {"home": 2, "away": 1},
    })
    fixtures[1].update({
        "id": "mock-pl-today-2",
        "startingAt": _mock_fixture_at(0, 12),
        "status": "upcoming",
    })
    fixtures[2].update({
        "id": "mock-pd-tomorrow-1",
        "startingAt": _mock_fixture_at(1, 12),
        "status": "upcoming",
    })
    fixtures[3].update({
        "id": "mock-sa-tomorrow-1",
        "startingAt": _mock_fixture_at(1, 11),
        "status": "upcoming",
    })
    return fixtures


# ── Auth ─────────────────────────────────────────────────────────────────────

def get_current_user(authorization: str | None = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header. Expected: Bearer <token>",
        )
    token = authorization.removeprefix("Bearer ").strip()
    claims = verify_id_token(token)
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Firebase ID token.",
        )
    return claims


# ── Public endpoints ──────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, Any]:
    """Liveness plus the two budgets worth watching: Gemini quota and the
    football-data.org request allowance reported by its response headers."""
    return {
        "status": "ok",
        "quota": quota.snapshot(),
        "football_data": _fdorg.snapshot(),
    }


# ── Fixture endpoints ─────────────────────────────────────────────────────────

@app.get("/api/fixtures")
def list_fixtures() -> dict[str, Any]:
    global _fixture_cache, _fixtures_ttl

    now = time.time()
    if _fixtures_ttl.get("data") and now - _fixtures_ttl.get("ts", 0) < FIXTURES_TTL_SECONDS:
        return {"status": "success", "data": _fixtures_ttl["data"], "source": "cache"}

    try:
        result = get_upcoming_fixtures()
        if result["status"] == "success" and result["data"]:
            normalized = result["data"]  # league_data_client returns normalized fixtures
            _fixture_cache = {f["id"]: f for f in normalized}
            _fixtures_ttl = {"data": normalized, "source": "football-data", "ts": now}
            return {"status": "success", "data": normalized, "source": result.get("source", "football-data")}
        provider_error = result.get("message", "football-data.org returned 0 fixtures")
    except Exception as exc:
        provider_error = f"football-data.org call failed: {exc}"

    # Fall back to mock — do NOT populate _fixtures_ttl so the next request retries the API
    mock_fixtures = _get_mock_fixtures()
    _fixture_cache = {f["id"]: f for f in mock_fixtures}
    return {"status": "success", "data": mock_fixtures, "source": "mock", "_diagnostic": provider_error}


@app.get("/api/fixtures/{match_id}")
def get_fixture(match_id: str) -> dict[str, Any]:
    if match_id in _fixture_cache:
        return {"status": "success", "data": _fixture_cache[match_id]}
    # Try football-data.org if the ID looks like an integer
    try:
        fixture_id = int(match_id)
        result = get_fixture_detail(fixture_id)
        if result["status"] == "success" and result["data"]:
            normalized = result["data"]
            _fixture_cache[match_id] = normalized
            return {"status": "success", "data": normalized}
    except (ValueError, Exception):
        pass
    raise HTTPException(status_code=404, detail="Fixture not found.")


def _report_failed_sections(fixture_id: int, results: dict[str, Any]) -> list[str]:
    """Return the names of sections whose fetch failed, printing why for each.

    Covers the sections the Gemini prompt relies on. A failure here (usually the
    football-data.org rate limit) would otherwise silently drop that section.
    """
    missing: list[str] = []
    for section, result in results.items():
        if isinstance(result, Exception):
            reason = f"{type(result).__name__}: {result}"
        elif isinstance(result, dict) and result.get("status") != "success":
            reason = result.get("message") or "request failed"
        else:
            continue
        missing.append(section)
        print(f"[Enrich] {section} unavailable for fixture {fixture_id}: {reason}")
    return missing


async def _gather_enriched(
    team_a_id: int, team_b_id: int,
    season_id: int | None, fixture_id_int: int,
) -> dict:
    """Fetch all enrichment data in parallel from football-data.org.

    Recent form: 2 x /teams/{id}/matches?status=FINISHED  (per team)
    Standings:   1 x /competitions/{code}/standings  (also yields per-team stats)
    Top scorers: 1 x /competitions/{code}/scorers
    Squad:       1 x /teams/{id}
    xG/lineups/injuries are not on the free tier — graceful empty payloads.
    season_id here is the football-data.org competition code (e.g. "PL").
    """
    from datetime import date, timedelta

    def _safe(fn, *args):
        try:
            return fn(*args)
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    today = date.today()
    # Replaced 8 guessed date calls with 2 direct team-specific calls.
    # /fixtures/between/{start}/{end}/{team_id} reliably returns completed
    # fixtures for any team/league without needing to guess game-day patterns.
    # Budget: 2 form + 1 standings + 1 xG = 4 enriched + 2 prediction = 6 ✓
    start_date = str(today - timedelta(days=60))
    end_date   = str(today)

    results = await asyncio.gather(
        asyncio.to_thread(_safe, get_fixtures_between_for_team, team_a_id, start_date, end_date, 5),
        asyncio.to_thread(_safe, get_fixtures_between_for_team, team_b_id, start_date, end_date, 5),
        asyncio.to_thread(_safe, get_season_standings, season_id),
        asyncio.to_thread(_safe, get_fixture_with_xg, fixture_id_int),
        # 3 new Gemini-context calls — feed into prompt only, never rendered by frontend
        # Budget: 4 existing + 3 new = 7 enriched + 2 prediction = 9 total ✓
        asyncio.to_thread(_safe, get_fixture_lineups, fixture_id_int, team_a_id, team_b_id),
        asyncio.to_thread(_safe, get_topscorers_with_names, season_id, 10),
        asyncio.to_thread(_safe, get_squad, team_a_id),
        return_exceptions=True,
    )

    def _ok(result: Any) -> Any:
        if isinstance(result, Exception):
            return None
        if isinstance(result, dict) and result.get("status") == "success":
            return result.get("data")
        return None

    form_a_r, form_b_r, standings_r, xg_r, lineups_r, topscorers_r, squad_a_r = results

    missing_sections = _report_failed_sections(fixture_id_int, {
        "team_a_recent_form":    form_a_r,
        "team_b_recent_form":    form_b_r,
        "standings":             standings_r,
        "topscorers_with_names": topscorers_r,
    })

    team_a_recent_form: list[dict] | None = _ok(form_a_r) or None
    team_b_recent_form: list[dict] | None = _ok(form_b_r) or None

    # Season stats derived from standings details (zero extra API calls)
    standings_list: list[dict] = _ok(standings_r) or []

    def _team_stats_from_standings(team_id: int) -> dict | None:
        row = next((r for r in standings_list if r.get("participant_id") == team_id), None)
        if not row:
            return None
        played = row.get("total_played") or 0
        gs = row.get("goals_scored")
        return {
            "goals_scored":   gs,
            "goals_conceded": row.get("goals_against"),
            "clean_sheets":   None,
            "wins":           row.get("won"),
            "draws":          row.get("drawn"),
            "losses":         row.get("lost"),
            "total_matches":  played,
            "avg_goals_per_game": round(gs / played, 2) if gs and played else None,
        }

    team_a_stats = _team_stats_from_standings(team_a_id)
    team_b_stats = _team_stats_from_standings(team_b_id)

    # Injuries are not on the free tier — show "Full squad available" for both
    # teams. The pluggable injury provider can fill this in when configured.
    injuries: dict = {"team_a": [], "team_b": []}

    xg_result = _ok(xg_r) or {}
    xg = xg_result.get("xg")
    trends = xg_result.get("trends")

    return {
        "team_a_recent_form": team_a_recent_form,
        "team_b_recent_form": team_b_recent_form,
        "standings":          standings_list,
        "team_a_stats":       team_a_stats,
        "team_b_stats":       team_b_stats,
        "injuries":           injuries,
        "xg":                 xg,
        "trends":             trends,
        "season_id":          season_id,
        # Gemini prompt context only — not read by the frontend
        "lineup":             _ok(lineups_r),
        "topscorers_with_names": _ok(topscorers_r),
        "squad_a":            _ok(squad_a_r),
        # Sections whose request failed (not ones that were legitimately empty).
        # The engine won't cache a prediction made with any of these missing.
        "missing_sections":   missing_sections,
    }


async def _shared_enrichment(match_id: str, fixture: dict, fixture_id_int: int) -> dict:
    """Gather enrichment for a match, joining a gather already in flight for it.

    Caches the result in _enriched_cache only when every section arrived, so a
    rate-limited, partial gather is retried next time instead of served forever.
    """
    task = _enrich_in_flight.get(match_id)
    if task is None:
        task = asyncio.create_task(_gather_enriched(
            fixture["homeTeam"]["id"], fixture["awayTeam"]["id"],
            fixture.get("seasonId"),
            fixture_id_int,
        ))
        _enrich_in_flight[match_id] = task
        task.add_done_callback(lambda _: _enrich_in_flight.pop(match_id, None))
    # shield: one client disconnecting must not cancel the gather another awaits.
    data = await asyncio.shield(task)
    if not data.get("missing_sections"):
        _enriched_cache[match_id] = {"data": data, "ts": time.time()}
    return data


def _cached_enrichment(match_id: str) -> dict | None:
    """Fresh cached enrichment for a match, or None if absent or expired."""
    entry = _enriched_cache.get(match_id)
    if entry is None:
        return None
    if time.time() - entry["ts"] >= ENRICHED_TTL_SECONDS:
        del _enriched_cache[match_id]
        return None
    return entry["data"]


@app.post("/api/fixtures/{match_id}/prediction")
async def fixture_prediction(
    match_id: str,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    if not _engine_available:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Prediction engine unavailable — GEMINI_API_KEY may not be set.",
        )

    # Allowlist + daily quota — the only endpoint that spends Gemini credit.
    quota_key = enforce_prediction_access(user)

    # Resolve fixture from cache, or try football-data.org
    fixture = _fixture_cache.get(match_id)
    if not fixture:
        try:
            fixture_id = int(match_id)
            result = get_fixture_detail(fixture_id)
            if result["status"] == "success" and result["data"]:
                fixture = result["data"]
                _fixture_cache[match_id] = fixture
        except (ValueError, Exception):
            pass

    if not fixture:
        quota.refund(quota_key)
        raise HTTPException(
            status_code=404,
            detail="Fixture not found. Call GET /api/fixtures first to seed the cache.",
        )

    home = fixture["homeTeam"]
    away = fixture["awayTeam"]

    # Gather enrichment data in parallel so Gemini can reason from it
    enriched_data: dict | None = None
    try:
        fixture_id_int = int(match_id)
    except ValueError:
        fixture_id_int = 0

    if not fixture.get("_isMock") and fixture_id_int:
        try:
            enriched_data = await _shared_enrichment(match_id, fixture, fixture_id_int)
        except Exception as exc:
            print(f"[Enrich] gathering failed for fixture {fixture_id_int}: {type(exc).__name__}: {exc}")
            enriched_data = None

    try:
        prediction = await asyncio.to_thread(
            _engine_generate_prediction,
            home["id"], away["id"], home["name"], away["name"],
            enriched_data,
        )
    except Exception as exc:
        quota.refund(quota_key)
        raise HTTPException(status_code=500, detail=f"Prediction engine error: {exc}")

    if prediction["status"] != "success":
        quota.refund(quota_key)
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {prediction.get('status', 'unknown')} — {prediction.get('message', '')}",
        )

    # Record the prediction in the SQLite history (best-effort).
    if _tracking_available:
        try:
            league_context = {
                "match_id":    str(match_id),
                "competition": fixture.get("leagueName") or fixture.get("seasonId") or "league",
                "stage":       None,
                "match_date":  (fixture.get("startingAt") or "")[:10] or None,
            }
            _tracking.log_prediction(league_context, home["name"], away["name"], prediction["data"])
        except Exception:
            pass

    return {"status": "success", "data": prediction["data"]}


@app.get("/api/fixtures/{match_id}/enriched")
async def fixture_enriched(
    match_id: str,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    # Serve from cache when the prediction endpoint already populated it
    cached = _cached_enrichment(match_id)
    if cached is not None:
        return {"status": "success", "data": cached}

    # Resolve fixture
    fixture = _fixture_cache.get(match_id)
    if not fixture:
        try:
            fixture_id = int(match_id)
            result = get_fixture_detail(fixture_id)
            if result["status"] == "success" and result["data"]:
                fixture = result["data"]
                _fixture_cache[match_id] = fixture
        except (ValueError, Exception):
            pass

    if not fixture:
        raise HTTPException(status_code=404, detail="Fixture not found.")

    _empty: dict = {k: None for k in [
        "team_a_recent_form", "team_b_recent_form", "standings",
        "team_a_stats", "team_b_stats", "topscorers", "injuries", "xg", "trends",
    ]}
    if fixture.get("_isMock"):
        return {"status": "success", "data": _empty}

    try:
        fixture_id_int = int(match_id)
    except ValueError:
        return {"status": "success", "data": _empty}

    data = await _shared_enrichment(match_id, fixture, fixture_id_int)
    return {"status": "success", "data": data}


# ── Auth verify ───────────────────────────────────────────────────────────────

@app.post("/api/auth/verify")
def verify_token(user: dict = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "uid": user.get("uid"),
            "email": user.get("email"),
            "email_verified": user.get("email_verified", False),
        },
    }


# ── Prediction tracking + analytics ───────────────────────────────────────────

def _resolve_finished_predictions() -> None:
    """Resolve outcomes for logged predictions from already-cached fixtures.

    Best-effort and budget-aware: it only reads finished fixtures that
    /api/fixtures already cached — it never makes extra football-data.org calls
    just to resolve, so analytics never burns the free-tier rate limit.
    """
    if not _tracking_available:
        return
    finished: list[dict] = []
    for f in (_fixtures_ttl.get("data") or []):
        if (f.get("status") or "").lower() == "finished" and f.get("score"):
            finished.append(f)
    if finished:
        try:
            _tracking.resolve_results(finished)
        except Exception:
            pass


@app.get("/api/analytics/calibration")
def get_calibration_endpoint(competition: str | None = None) -> dict[str, Any]:
    """Accuracy / Brier / log-loss / ECE over resolved predictions.

    Optional `competition` filter (e.g. Premier League). Omit for all.
    """
    if not _tracking_available:
        return {"status": "unavailable", "message": "Prediction tracking is not enabled."}
    try:
        _resolve_finished_predictions()
        return {"status": "success", "data": _tracking.calibration_report(competition)}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@app.get("/api/analytics/betting")
def get_betting_endpoint(competition: str | None = None) -> dict[str, Any]:
    """ROI / win-rate / average-edge / CLV over resolved value bets."""
    if not _tracking_available:
        return {"status": "unavailable", "message": "Prediction tracking is not enabled."}
    try:
        _resolve_finished_predictions()
        return {"status": "success", "data": _tracking.betting_report(competition)}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@app.get("/api/analytics")
def get_analytics_endpoint(competition: str | None = None) -> dict[str, Any]:
    """Combined analytics payload across all competitions.

    Summary + reliability bins + over-time series. Optional `competition` filter.
    """
    if not _tracking_available:
        return {"status": "unavailable", "message": "Prediction tracking is not enabled."}
    try:
        _resolve_finished_predictions()
        return {"status": "success", "data": _tracking.analytics_report(competition)}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@app.get("/api/predictions/{match_id}/history")
def get_prediction_history_endpoint(match_id: str) -> dict[str, Any]:
    """All stored predictions for a match (across model variants), with outcomes."""
    if not _tracking_available:
        return {"status": "unavailable", "message": "Prediction tracking is not enabled."}
    try:
        from storage import prediction_db
        rows = [r for r in prediction_db.read_rows() if str(r.get("match_id")) == str(match_id)]
        return {"status": "success", "data": rows}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
