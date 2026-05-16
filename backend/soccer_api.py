from typing import Any
import requests
from backend.config import APIFOOTBALL_API_KEY, APIFOOTBALL_BASE_URL

MOCK_TEAMS = [
    {"id": 33, "name": "Argentina", "country": "Argentina"},
    {"id": 2, "name": "France", "country": "France"},
    {"id": 6, "name": "Brazil", "country": "Brazil"},
    {"id": 9, "name": "Spain", "country": "Spain"},
    {"id": 27, "name": "Germany", "country": "Germany"},
]

MOCK_STATS: dict[int, dict[str, float]] = {
    33: {"attack": 8.5, "defense": 8.1, "recent_form": 4.2},
    2:  {"attack": 7.8, "defense": 8.3, "recent_form": 3.6},
    6:  {"attack": 8.2, "defense": 7.9, "recent_form": 3.8},
    9:  {"attack": 7.6, "defense": 8.0, "recent_form": 3.5},
    27: {"attack": 7.4, "defense": 7.7, "recent_form": 3.2},
}


class SoccerApiClient:
    def __init__(self) -> None:
        self._headers = {
            "x-rapidapi-host": "v3.football.api-sports.io",
            "x-rapidapi-key": APIFOOTBALL_API_KEY,
        }

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{APIFOOTBALL_BASE_URL}/{endpoint}"
        response = requests.get(url, headers=self._headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_teams(self) -> list[dict[str, Any]]:
        if not APIFOOTBALL_API_KEY:
            return MOCK_TEAMS
        try:
            data = self._get("teams", {"league": "1", "season": "2023"})
            return [
                {
                    "id": t["team"]["id"],
                    "name": t["team"]["name"],
                    "country": t["team"]["country"],
                }
                for t in data.get("response", [])
            ]
        except Exception:
            return MOCK_TEAMS

    def get_team_stats(self, team_id: int) -> dict[str, float]:
        if not APIFOOTBALL_API_KEY:
            return MOCK_STATS.get(team_id, {"attack": 7.0, "defense": 7.0, "recent_form": 3.0})
        try:
            data = self._get("teams/statistics", {"team": team_id, "league": "1", "season": "2023"})
            resp = data.get("response", {})
            goals_for = resp.get("goals", {}).get("for", {}).get("average", {}).get("total", "7.0")
            goals_against = resp.get("goals", {}).get("against", {}).get("average", {}).get("total", "7.0")
            fixtures = resp.get("fixtures", {})
            wins = fixtures.get("wins", {}).get("total", 0) or 0
            total = fixtures.get("played", {}).get("total", 1) or 1
            attack = min(10.0, float(goals_for) * 2)
            defense = max(0.0, 10.0 - float(goals_against) * 2)
            recent_form = round((wins / total) * 5, 1)
            return {"attack": round(attack, 1), "defense": round(defense, 1), "recent_form": recent_form}
        except Exception:
            return MOCK_STATS.get(team_id, {"attack": 7.0, "defense": 7.0, "recent_form": 3.0})

    def get_team_name(self, team_id: int) -> str:
        for team in MOCK_TEAMS:
            if team["id"] == team_id:
                return team["name"]
        return f"Team {team_id}"
