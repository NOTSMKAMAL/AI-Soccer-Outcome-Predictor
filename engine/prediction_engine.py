import os
from dotenv import load_dotenv
from google import genai
from storage.sportmonks_client import check_team_data, get_head_to_head, get_recent_fixtures

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def prepare_matchup(team_a_id: int, team_b_id: int) -> dict:
    if team_a_id == team_b_id:
        return {"status": "same_team_selected"}
    result = check_team_data(team_a_id, team_b_id)
    if result["status"] != "success":
        return {"status": "insufficient_data"}
    return {"status": "success", "data": {"matchup_id": f"{team_a_id}_vs_{team_b_id}"}}


def compare_matchup(team_a_id: int, team_b_id: int,
                    team_a_name: str, team_b_name: str) -> dict:
    h2h = get_head_to_head(team_a_id, team_b_id)

    if h2h["status"] == "error":
        return {"status": "incomplete_data"}

    h2h_data = h2h.get("data", [])
    wins_a = 0
    wins_b = 0
    draws = 0
    recent_results = []

    for match in h2h_data:
        result_info = (match.get("result_info") or "").lower()
        if team_a_name.lower() in result_info:
            wins_a += 1
        elif team_b_name.lower() in result_info:
            wins_b += 1
        else:
            draws += 1
        recent_results.append({
            "name": match.get("name", ""),
            "date": match.get("starting_at", "")[:10],
            "result_info": match.get("result_info", ""),
        })

    return {
        "status": "success",
        "data": {
            "team_a_wins": wins_a,
            "team_b_wins": wins_b,
            "draws": draws,
            "total_h2h": len(h2h_data),
            "recent_results": recent_results[:5],
        },
    }


def generate_prediction(team_a_id: int, team_b_id: int,
                        team_a_name: str, team_b_name: str) -> dict:
    comparison = compare_matchup(team_a_id, team_b_id, team_a_name, team_b_name)
    if comparison["status"] != "success":
        return {"status": "prediction_error"}

    data = comparison["data"]

    if data["recent_results"]:
        results_lines = "\n".join(
            f"  - {r['name']} ({r['date']}): {r['result_info']}"
            for r in data["recent_results"]
        )
        h2h_section = (
            f"Head-to-head record: {team_a_name} {data['team_a_wins']}W "
            f"/ {team_b_name} {data['team_b_wins']}W / {data['draws']} draws "
            f"({data['total_h2h']} total)\n"
            f"Recent results:\n{results_lines}"
        )
    else:
        h2h_section = (
            "No head-to-head history exists between these teams in the database. "
            "Use your general knowledge of these MLS teams to make a prediction."
        )

    prompt = f"""
You are a sports analyst AI. Based on the data below, predict which team is more likely to win.

Team A: {team_a_name}
Team B: {team_b_name}

{h2h_section}

Respond in this exact format:
Winner: <team name>
Confidence: <low | medium | high>
Reasoning: <2-3 sentences explaining the key factors>
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        raw = response.text

        lines = {
            line.split(":")[0].strip(): ":".join(line.split(":")[1:]).strip()
            for line in raw.strip().splitlines() if ":" in line
        }

        return {
            "status": "success",
            "data": {
                "winner": lines.get("Winner", "Unknown"),
                "confidence": lines.get("Confidence", "low"),
                "reasoning": lines.get("Reasoning", ""),
            },
        }
    except Exception as e:
        return {"status": "reasoning_failed", "message": str(e)}
