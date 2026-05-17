from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.soccer_api import SoccerApiClient, MOCK_TEAMS
from backend.agent import run_prediction_agent
from backend.firebase_config import verify_id_token
from backend.firebase_db import delete_prediction, get_user_predictions, save_prediction
from storage.sportmonks_client import (
    get_upcoming_mls_fixtures,
    get_fixture_detail,
    LEAGUE_IDS,
    LEAGUE_NAMES,
    _parse_scores,
)

# Lazy import — engine needs GEMINI_API_KEY; catch missing-key errors at call time
try:
    from engine.prediction_engine import generate_prediction as _engine_generate_prediction
    _engine_available = True
except Exception:
    _engine_available = False

app = FastAPI(title="AI Sports Outcome Predictor", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

soccer_client = SoccerApiClient()

# ── In-memory fixture cache (populated on GET /api/fixtures) ──────────────────
_fixture_cache: dict[str, dict] = {}

# Mock MLS fixtures used when SportMonks returns no data.
# These IDs are NOT real SportMonks IDs — prediction will fail gracefully for them.
MOCK_MLS_FIXTURES: list[dict] = [
    {
        "id": "mock-mls-1",
        "name": "LA Galaxy vs LAFC",
        "homeTeam": {"id": 246, "name": "LA Galaxy"},
        "awayTeam": {"id": 1436, "name": "LAFC"},
        "startingAt": "2025-06-01 02:30:00",
        "leagueId": 779,
        "leagueName": "MLS",
        "status": "upcoming",
        "_isMock": True,
    },
    {
        "id": "mock-mls-2",
        "name": "Inter Miami CF vs Atlanta United",
        "homeTeam": {"id": 14163, "name": "Inter Miami CF"},
        "awayTeam": {"id": 13847, "name": "Atlanta United"},
        "startingAt": "2025-06-01 23:00:00",
        "leagueId": 779,
        "leagueName": "MLS",
        "status": "upcoming",
        "_isMock": True,
    },
    {
        "id": "mock-mls-3",
        "name": "Seattle Sounders vs Portland Timbers",
        "homeTeam": {"id": 13862, "name": "Seattle Sounders"},
        "awayTeam": {"id": 13868, "name": "Portland Timbers"},
        "startingAt": "2025-06-02 03:00:00",
        "leagueId": 779,
        "leagueName": "MLS",
        "status": "upcoming",
        "_isMock": True,
    },
    {
        "id": "mock-mls-4",
        "name": "NYC FC vs Red Bull New York",
        "homeTeam": {"id": 13868, "name": "NYC FC"},
        "awayTeam": {"id": 347, "name": "Red Bull New York"},
        "startingAt": "2025-06-03 00:00:00",
        "leagueId": 779,
        "leagueName": "MLS",
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


def _get_mock_mls_fixtures() -> list[dict]:
    fixtures = [dict(f) for f in MOCK_MLS_FIXTURES]
    fixtures[0].update(
        {
            "id": "mock-mls-today-1",
            "startingAt": _mock_fixture_at(0, 14),
            "status": "finished",
            "score": {"home": 2, "away": 1},
        }
    )
    fixtures[1].update(
        {
            "id": "mock-mls-today-2",
            "startingAt": _mock_fixture_at(0, 19),
            "status": "upcoming",
        }
    )
    fixtures[2].update(
        {
            "id": "mock-mls-tomorrow-1",
            "startingAt": _mock_fixture_at(1, 17),
            "status": "upcoming",
        }
    )
    fixtures[3].update(
        {
            "id": "mock-mls-tomorrow-2",
            "homeTeam": {"id": 13869, "name": "NYC FC"},
            "startingAt": _mock_fixture_at(1, 20),
            "status": "upcoming",
        }
    )
    return fixtures


def _normalize_fixture(sm_fixture: dict) -> dict:
    """Convert a raw SportMonks v3 fixture dict to our API shape.

    Reads league and state from the SportMonks `include=league;state` response
    objects when present, with safe fallbacks for subscriptions that don't
    return those includes.
    """
    participants = sm_fixture.get("participants") or []
    home = next(
        (p for p in participants if (p.get("meta") or {}).get("location") == "home"),
        participants[0] if participants else {},
    )
    away = next(
        (p for p in participants if (p.get("meta") or {}).get("location") == "away"),
        participants[1] if len(participants) > 1 else {},
    )

    # League — prefer the included object, fall back to the raw league_id field
    league_obj = sm_fixture.get("league") or {}
    league_id: int = (
        sm_fixture.get("league_id")
        or league_obj.get("id")
        or LEAGUE_IDS["mls"]
    )
    league_name: str = (
        league_obj.get("name")
        or league_obj.get("short_code")
        or LEAGUE_NAMES.get(league_id, f"League {league_id}")
    )

    # Status — prefer the included state object's short name
    state_obj = sm_fixture.get("state") or {}
    match_status: str = (
        state_obj.get("short_name")
        or state_obj.get("name")
        or "NS"
    )

    # Scores — only present when the `scores` include was requested
    scores_list = sm_fixture.get("scores") or []
    score = _parse_scores(scores_list)

    venue_obj = sm_fixture.get("venue") or {}
    venue_name: str | None = venue_obj.get("name") or None

    normalized: dict = {
        "id": str(sm_fixture.get("id", "")),
        "name": sm_fixture.get("name", ""),
        "homeTeam": {
            "id": home.get("id", 0),
            "name": home.get("name", "Unknown"),
            "logo": home.get("image_path") or None,
        },
        "awayTeam": {
            "id": away.get("id", 0),
            "name": away.get("name", "Unknown"),
            "logo": away.get("image_path") or None,
        },
        "startingAt": sm_fixture.get("starting_at", ""),
        "leagueId": league_id,
        "leagueName": league_name,
        "status": match_status,
        "venue": venue_name,
        "_isMock": False,
    }
    if score is not None:
        normalized["score"] = score
    return normalized


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


# ── Request / response models ─────────────────────────────────────────────────

class PredictRequest(BaseModel):
    team_a_id: int
    team_b_id: int


class SavePredictionRequest(BaseModel):
    fixture_id: int | None = None
    home_team: str
    away_team: str
    predicted_winner: str
    confidence: int
    reasoning: str
    match_datetime: str | None = None


# ── Public endpoints ──────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/teams")
def get_teams() -> dict[str, Any]:
    try:
        teams = soccer_client.get_teams()
        return {"status": "success", "data": teams}
    except Exception:
        return {"status": "success", "data": MOCK_TEAMS}


@app.post("/api/predict")
def predict(body: PredictRequest) -> dict[str, Any]:
    if body.team_a_id == body.team_b_id:
        raise HTTPException(status_code=400, detail="Team A and Team B must be different.")
    try:
        result = run_prediction_agent(body.team_a_id, body.team_b_id)
        return {"status": "success", "data": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Fixture endpoints ─────────────────────────────────────────────────────────

@app.get("/api/fixtures")
def list_fixtures() -> dict[str, Any]:
    global _fixture_cache

    sportmonks_error: str | None = None
    try:
        result = get_upcoming_mls_fixtures()
        if result["status"] == "success" and result["data"]:
            normalized = [_normalize_fixture(f) for f in result["data"]]
            _fixture_cache = {f["id"]: f for f in normalized}
            return {"status": "success", "data": normalized, "source": "sportmonks"}
        # SportMonks returned an error dict or an empty list
        sportmonks_error = result.get("message", "SportMonks returned 0 fixtures (status 200)")
    except Exception as exc:
        sportmonks_error = f"Unexpected error calling SportMonks: {exc}"

    # Fallback: return mock fixtures so the dashboard is never completely empty,
    # but include _diagnostic so callers can see exactly why real data failed.
    mock_fixtures = _get_mock_mls_fixtures()
    _fixture_cache = {f["id"]: f for f in mock_fixtures}
    return {
        "status": "success",
        "data": mock_fixtures,
        "source": "mock",
        "_diagnostic": sportmonks_error,
    }


@app.get("/api/fixtures/{match_id}")
def get_fixture(match_id: str) -> dict[str, Any]:
    if match_id in _fixture_cache:
        return {"status": "success", "data": _fixture_cache[match_id]}
    # Try SportMonks if the ID looks like an integer
    try:
        fixture_id = int(match_id)
        result = get_fixture_detail(fixture_id)
        if result["status"] == "success" and result["data"]:
            normalized = _normalize_fixture(result["data"])
            _fixture_cache[match_id] = normalized
            return {"status": "success", "data": normalized}
    except (ValueError, Exception):
        pass
    raise HTTPException(status_code=404, detail="Fixture not found.")


@app.post("/api/fixtures/{match_id}/prediction")
def fixture_prediction(
    match_id: str,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    if not _engine_available:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Prediction engine unavailable — GEMINI_API_KEY may not be set.",
        )

    # Resolve fixture from cache, or try SportMonks
    fixture = _fixture_cache.get(match_id)
    if not fixture:
        try:
            fixture_id = int(match_id)
            result = get_fixture_detail(fixture_id)
            if result["status"] == "success" and result["data"]:
                fixture = _normalize_fixture(result["data"])
                _fixture_cache[match_id] = fixture
        except (ValueError, Exception):
            pass

    if not fixture:
        raise HTTPException(
            status_code=404,
            detail="Fixture not found. Call GET /api/fixtures first to seed the cache.",
        )

    home = fixture["homeTeam"]
    away = fixture["awayTeam"]

    try:
        prediction = _engine_generate_prediction(
            home["id"], away["id"], home["name"], away["name"]
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prediction engine error: {exc}")

    if prediction["status"] != "success":
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {prediction.get('status', 'unknown')} — {prediction.get('message', '')}",
        )

    return {"status": "success", "data": prediction["data"]}


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


# ── Protected prediction history endpoints ────────────────────────────────────

@app.post("/api/predictions", status_code=status.HTTP_201_CREATED)
def create_prediction(
    body: SavePredictionRequest,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    user_id: str = user["uid"]
    doc_id = save_prediction(user_id, body.model_dump())
    if doc_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firestore is not configured or unavailable.",
        )
    return {"status": "success", "data": {"id": doc_id}}


@app.get("/api/predictions")
def list_predictions(user: dict = Depends(get_current_user)) -> dict[str, Any]:
    user_id: str = user["uid"]
    predictions = get_user_predictions(user_id)
    return {"status": "success", "data": predictions}


@app.delete("/api/predictions/{prediction_id}", status_code=status.HTTP_200_OK)
def remove_prediction(
    prediction_id: str,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    deleted = delete_prediction(prediction_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found or already deleted.",
        )
    return {"status": "success", "data": {"id": prediction_id}}
