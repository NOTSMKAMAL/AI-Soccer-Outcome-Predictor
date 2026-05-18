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


def _form_label(fixtures: list[dict], winner_name: str) -> tuple[str, int]:
    """Return (W/D/L sequence string, win_rate_pct) from a list of recent fixtures."""
    symbols = []
    for f in fixtures:
        ri = (f.get("result_info") or "").lower()
        if winner_name.lower() in ri and "won" in ri:
            symbols.append("W")
        elif "draw" in ri or "drew" in ri:
            symbols.append("D")
        else:
            symbols.append("L")
    if not symbols:
        return "", 0
    win_rate = int(symbols.count("W") / len(symbols) * 100)
    return "/".join(symbols), win_rate


def _build_enriched_section(
    team_a_name: str, team_b_name: str,
    team_a_id: int, team_b_id: int,
    enriched: dict,
) -> str:
    """Build the enriched data block appended to the Gemini prompt."""
    parts: list[str] = []

    # Recent form
    form_a = enriched.get("team_a_recent_form") or []
    form_b = enriched.get("team_b_recent_form") or []
    if form_a or form_b:
        seq_a, wr_a = _form_label(form_a, team_a_name)
        seq_b, wr_b = _form_label(form_b, team_b_name)
        parts.append(
            f"RECENT FORM (last 5 matches):\n"
            f"  - {team_a_name}: {seq_a or 'N/A'} — {wr_a}% win rate\n"
            f"  - {team_b_name}: {seq_b or 'N/A'} — {wr_b}% win rate"
        )

    # League standings
    standings = enriched.get("standings") or []
    if standings:
        pos_a = next((r for r in standings if r.get("participant_id") == team_a_id), None)
        pos_b = next((r for r in standings if r.get("participant_id") == team_b_id), None)

        def _sl(name: str, pos: dict | None) -> str:
            if not pos:
                return f"  - {name}: Standing not found"
            return (
                f"  - {name}: {pos.get('position', '?')}th, "
                f"{pos.get('points', 'N/A')} pts, "
                f"GD {pos.get('goal_difference', 'N/A')}, "
                f"form: {pos.get('form', 'N/A')}"
            )

        parts.append(
            f"CURRENT LEAGUE STANDINGS:\n{_sl(team_a_name, pos_a)}\n{_sl(team_b_name, pos_b)}"
        )

    # Season stats
    sa = enriched.get("team_a_stats") or {}
    sb = enriched.get("team_b_stats") or {}
    if sa or sb:
        def _stat(name: str, s: dict) -> str:
            if not s:
                return f"  - {name}: No season stats available"
            return (
                f"  - {name}: {s.get('goals_scored', 'N/A')} scored, "
                f"{s.get('goals_conceded', 'N/A')} conceded, "
                f"{s.get('clean_sheets', 'N/A')} clean sheets, "
                f"{s.get('wins', 'N/A')}W/{s.get('draws', 'N/A')}D/{s.get('losses', 'N/A')}L"
            )
        parts.append(
            f"SEASON STATISTICS:\n{_stat(team_a_name, sa)}\n{_stat(team_b_name, sb)}"
        )

    # xG
    xg = enriched.get("xg") or {}
    if xg:
        xg_a = xg.get("team_a_xg")
        xg_b = xg.get("team_b_xg")
        if xg_a is not None and xg_b is not None:
            parts.append(
                f"xG PERFORMANCE (expected goals — quality of chances created):\n"
                f"  - {team_a_name} xG: {xg_a}\n"
                f"  - {team_b_name} xG: {xg_b}\n"
                f"  xG above actual goals = underperforming; below = overperforming.\n"
                f"  Factor this into your confidence level."
            )

    # Trends
    trends = enriched.get("trends") or {}
    ta_tr = trends.get("team_a") or []
    tb_tr = trends.get("team_b") or []
    if ta_tr or tb_tr:
        parts.append(
            f"CURRENT TRENDS:\n"
            f"  - {team_a_name}: {', '.join(ta_tr) if ta_tr else 'none'}\n"
            f"  - {team_b_name}: {', '.join(tb_tr) if tb_tr else 'none'}"
        )

    # Injuries
    injuries = enriched.get("injuries") or {}
    inj_a = injuries.get("team_a") or []
    inj_b = injuries.get("team_b") or []
    if injuries:
        def _inj(name: str, lst: list) -> str:
            if not lst:
                return f"  - {name}: Full squad available"
            names = [i.get("player_name", "Unknown") for i in lst]
            return f"  - {name} missing: {', '.join(names)}"
        parts.append(
            f"INJURY & SUSPENSION NEWS:\n{_inj(team_a_name, inj_a)}\n{_inj(team_b_name, inj_b)}"
        )

    # Top scorers
    topscorers = enriched.get("topscorers") or []
    if topscorers:
        scorer_lines = []
        for s in topscorers:
            flag = ""
            if s.get("team_id") in (team_a_id, team_b_id):
                flag = " ← PLAYING TODAY"
            scorer_lines.append(
                f"  {s.get('player_name', '?')} ({s.get('team_name', '?')}): "
                f"{s.get('goals', 0)} goals, {s.get('assists', 0)} assists{flag}"
            )
        parts.append("TOP SCORERS IN THIS LEAGUE:\n" + "\n".join(scorer_lines))

    return "\n\n".join(parts)


def generate_prediction(
    team_a_id: int, team_b_id: int,
    team_a_name: str, team_b_name: str,
    enriched_data: dict = None,
) -> dict:
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
            f"HEAD-TO-HEAD HISTORY ({data['total_h2h']} matches):\n"
            f"  - {team_a_name}: {data['team_a_wins']} wins\n"
            f"  - {team_b_name}: {data['team_b_wins']} wins\n"
            f"  - Draws: {data['draws']}\n"
            f"Recent results:\n{results_lines}"
        )
    else:
        h2h_section = (
            "No head-to-head history exists between these teams in the database. "
            "Use your general knowledge of these MLS teams to make a prediction."
        )

    if enriched_data:
        enriched_section = _build_enriched_section(
            team_a_name, team_b_name, team_a_id, team_b_id, enriched_data
        )
        data_block = f"{h2h_section}\n\n{enriched_section}"
        response_format = (
            "Respond in this exact format:\n"
            "Winner: <team name>\n"
            "Confidence: <low | medium | high>\n"
            "Reasoning: <4-5 sentences. Each sentence must reference a specific statistic "
            "from the data above. Do not use generic phrases without citing actual numbers.>\n"
            "Key Factor 1: <title> | <one sentence with specific stat>\n"
            "Key Factor 2: <title> | <one sentence with specific stat>\n"
            "Key Factor 3: <title> | <one sentence with specific stat>"
        )
    else:
        data_block = h2h_section
        response_format = (
            "Respond in this exact format:\n"
            "Winner: <team name>\n"
            "Confidence: <low | medium | high>\n"
            "Reasoning: <2-3 sentences explaining the key factors>"
        )

    prompt = f"""You are a professional sports analyst AI for the AI Sports Outcome Predictor.
Analyze ALL data below and predict the winner. Your reasoning MUST cite specific statistics.

Team A: {team_a_name}
Team B: {team_b_name}

{data_block}

{response_format}
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        raw = response.text

        # Multi-line aware parser
        parsed: dict[str, str] = {}
        current_key: str | None = None
        current_val_lines: list[str] = []
        known_keys = {"Winner", "Confidence", "Reasoning",
                      "Key Factor 1", "Key Factor 2", "Key Factor 3"}

        for line in raw.strip().splitlines():
            stripped = line.strip()
            matched_key = None
            for k in known_keys:
                if stripped.startswith(f"{k}:"):
                    matched_key = k
                    break
            if matched_key:
                if current_key:
                    parsed[current_key] = " ".join(current_val_lines).strip()
                current_key = matched_key
                current_val_lines = [stripped[len(matched_key) + 1:].strip()]
            elif current_key:
                current_val_lines.append(stripped)
        if current_key:
            parsed[current_key] = " ".join(current_val_lines).strip()

        def _parse_kf(raw_str: str) -> dict | None:
            if not raw_str:
                return None
            parts = raw_str.split("|", 1)
            return {
                "title": parts[0].strip(),
                "text": parts[1].strip() if len(parts) > 1 else raw_str.strip(),
            }

        result_data: dict = {
            "winner": parsed.get("Winner", "Unknown"),
            "confidence": parsed.get("Confidence", "low"),
            "reasoning": parsed.get("Reasoning", ""),
            "headToHead": {
                "teamAWins": data["team_a_wins"],
                "teamBWins": data["team_b_wins"],
                "draws": data["draws"],
                "total": data["total_h2h"],
                "recentResults": data["recent_results"],
            },
        }
        kf1 = _parse_kf(parsed.get("Key Factor 1", ""))
        kf2 = _parse_kf(parsed.get("Key Factor 2", ""))
        kf3 = _parse_kf(parsed.get("Key Factor 3", ""))
        key_factors = [kf for kf in (kf1, kf2, kf3) if kf]
        if key_factors:
            result_data["keyFactors"] = key_factors

        return {"status": "success", "data": result_data}
    except Exception as e:
        return {"status": "reasoning_failed", "message": str(e)}
