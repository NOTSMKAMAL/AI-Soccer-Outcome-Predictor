import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.sportmonks.com/v3/football"
API_KEY = os.getenv("SPORTMONKS_API_KEY")

HEADERS = {
    "Authorization": API_KEY
}

# League IDs from your SportMonks subscription
LEAGUE_IDS = {
    "premier_league": 8,
    "ligue_1": 301,
    "la_liga": 564,
    "serie_a": 384,
    "mls": 779,
}


def get_team_stats(team_id: int) -> dict:
    """Fetch basic team info and stats by team ID."""
    try:
        url = f"{BASE_URL}/teams/{team_id}"
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        return {"status": "success", "data": resp.json().get("data", {})}
    except requests.exceptions.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Request failed: {e}"}


def get_head_to_head(team_a_id: int, team_b_id: int) -> dict:
    """Fetch head-to-head fixture history between two teams."""
    try:
        url = f"{BASE_URL}/fixtures/head-to-head/{team_a_id}/{team_b_id}"
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        return {"status": "success", "data": resp.json().get("data", [])}
    except requests.exceptions.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Request failed: {e}"}


def get_recent_fixtures(team_id: int, limit: int = 5) -> dict:
    """Fetch recent fixtures for a team to evaluate recent form."""
    try:
        url = f"{BASE_URL}/fixtures"
        params = {
            "filter[team_id]": team_id,
            "per_page": limit,
            "sort": "-starting_at",
        }
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        return {"status": "success", "data": resp.json().get("data", [])}
    except requests.exceptions.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Request failed: {e}"}


def check_team_data(team_a_id: int, team_b_id: int) -> dict:
    """Verify both teams exist and have accessible data (used by engine layer)."""
    result_a = get_team_stats(team_a_id)
    result_b = get_team_stats(team_b_id)

    team_a_ready = result_a["status"] == "success" and bool(result_a["data"])
    team_b_ready = result_b["status"] == "success" and bool(result_b["data"])

    if not team_a_ready or not team_b_ready:
        return {"status": "team_not_found"}

    return {
        "status": "success",
        "data": {"team_a_ready": team_a_ready, "team_b_ready": team_b_ready},
    }