from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.soccer_api import SoccerApiClient, MOCK_TEAMS
from backend.agent import run_prediction_agent

app = FastAPI(title="AI Sports Outcome Predictor", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

soccer_client = SoccerApiClient()


class PredictRequest(BaseModel):
    team_a_id: int
    team_b_id: int


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/teams")
def get_teams() -> dict[str, Any]:
    try:
        teams = soccer_client.get_teams()
        return {"status": "success", "data": teams}
    except Exception as exc:
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
