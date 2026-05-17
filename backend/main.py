from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.soccer_api import SoccerApiClient, MOCK_TEAMS
from backend.agent import run_prediction_agent
from backend.firebase_config import verify_id_token
from backend.firebase_db import delete_prediction, get_user_predictions, save_prediction

app = FastAPI(title="AI Sports Outcome Predictor", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

soccer_client = SoccerApiClient()


# ── Auth ─────────────────────────────────────────────────────────────────────

def get_current_user(authorization: str | None = Header(None)) -> dict:
    """
    FastAPI dependency that validates a Firebase Bearer token.

    Raises 401 if the header is missing, malformed, or the token is invalid.
    Returns the decoded token claims dict on success.
    """
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


# ── Fixture stub endpoints ────────────────────────────────────────────────────
# These will be wired to storage/sportmonks_client.py and
# engine/prediction_engine.py once the main-branch layer is merged here.

@app.get("/api/fixtures")
def list_fixtures() -> dict[str, Any]:
    # TODO: delegate to storage/sportmonks_client.py after merge
    return {"status": "success", "data": []}


@app.get("/api/fixtures/{match_id}")
def get_fixture(match_id: str) -> dict[str, Any]:
    # TODO: delegate to storage/sportmonks_client.py after merge
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Fixture detail not yet implemented — pending engine/storage merge.",
    )


@app.post("/api/fixtures/{match_id}/prediction")
def fixture_prediction(
    match_id: str,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    # TODO: delegate to engine/prediction_engine.py after merge
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Fixture prediction not yet implemented — pending engine/storage merge.",
    )


@app.post("/api/auth/verify")
def verify_token(user: dict = Depends(get_current_user)) -> dict[str, Any]:
    """Verify a Firebase ID token and return the decoded uid / email."""
    return {
        "status": "success",
        "data": {
            "uid": user.get("uid"),
            "email": user.get("email"),
            "email_verified": user.get("email_verified", False),
        },
    }


# ── Protected prediction endpoints ────────────────────────────────────────────

@app.post("/api/predictions", status_code=status.HTTP_201_CREATED)
def create_prediction(
    body: SavePredictionRequest,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Save a prediction for the authenticated user."""
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
    """Return all predictions for the authenticated user, newest first."""
    user_id: str = user["uid"]
    predictions = get_user_predictions(user_id)
    return {"status": "success", "data": predictions}


@app.delete("/api/predictions/{prediction_id}", status_code=status.HTTP_200_OK)
def remove_prediction(
    prediction_id: str,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Delete a prediction by ID (must belong to the authenticated user)."""
    deleted = delete_prediction(prediction_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found or already deleted.",
        )
    return {"status": "success", "data": {"id": prediction_id}}
