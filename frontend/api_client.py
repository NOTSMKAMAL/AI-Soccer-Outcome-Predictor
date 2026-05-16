from typing import Any
import requests

BACKEND_URL = "http://localhost:8000"

MOCK_TEAMS = [
    {"id": 33, "name": "Argentina", "country": "Argentina"},
    {"id": 2, "name": "France", "country": "France"},
    {"id": 6, "name": "Brazil", "country": "Brazil"},
    {"id": 9, "name": "Spain", "country": "Spain"},
    {"id": 27, "name": "Germany", "country": "Germany"},
]

MOCK_PREDICTION = {
    "status": "success",
    "data": {
        "teams": {
            "team_a": {"id": 33, "name": "Argentina"},
            "team_b": {"id": 2, "name": "France"},
        },
        "winner": "Argentina",
        "confidence": 72,
        "reasoning": (
            "Argentina shows superior recent form with 4 wins in last 5 matches compared to France's "
            "3 wins. Attack strength favors Argentina (8.5/10 vs 7.8/10), though France has a slight "
            "defensive edge (8.3/10 vs 8.1/10)."
        ),
        "comparison": {
            "attack": {"argentina": 8.5, "france": 7.8},
            "defense": {"argentina": 8.1, "france": 8.3},
            "recent_form": {"argentina": 4.2, "france": 3.6},
        },
    },
}


def get_teams() -> list[dict[str, Any]]:
    try:
        response = requests.get(f"{BACKEND_URL}/api/teams", timeout=5)
        response.raise_for_status()
        data = response.json()
        return data.get("data", MOCK_TEAMS)
    except Exception:
        return MOCK_TEAMS


def get_prediction(team_a_id: int, team_b_id: int) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/predict",
            json={"team_a_id": team_a_id, "team_b_id": team_b_id},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()
    except Exception:
        mock = MOCK_PREDICTION.copy()
        mock["data"] = dict(mock["data"])
        mock["data"]["teams"] = {
            "team_a": {"id": team_a_id, "name": _team_name(team_a_id)},
            "team_b": {"id": team_b_id, "name": _team_name(team_b_id)},
        }
        return mock


def _team_name(team_id: int) -> str:
    for team in MOCK_TEAMS:
        if team["id"] == team_id:
            return team["name"]
    return f"Team {team_id}"
