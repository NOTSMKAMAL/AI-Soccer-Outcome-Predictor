import math
import os
from datetime import date as _date
from dotenv import load_dotenv
from google import genai
from google.genai import types
from storage.sportmonks_client import check_team_data, get_head_to_head, get_recent_fixtures, get_season_team_stats

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

_season_stats_cache: dict[int, dict] = {}

# Per-league home advantage coefficients (Dixon-Coles research)
# MLS lower due to large travel distances and weaker crowd effects
_HOME_ADVANTAGE = {
    8:   1.18,   # Premier League — strong home crowds
    564: 1.16,   # La Liga — strong home support
    384: 1.15,   # Serie A — standard home advantage
    301: 1.13,   # Ligue 1 — slightly below average
    779: 1.08,   # MLS — weakest due to travel distances
}
_HOME_ADVANTAGE_DEFAULT = 1.15  # fallback for unknown leagues


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


def dixon_coles_probability(
    team_a_stats: dict,
    team_b_stats: dict,
    is_home_a: bool = True,
    rho: float = -0.1,
    home_advantage: float = 1.15,
    max_goals: int = 10,
    season_id: int | None = None,
    team_a_id: int | None = None,
    team_b_id: int | None = None,
    league_id: int | None = None,
    rolling_form: dict | None = None,
) -> dict | None:
    """Dixon-Coles adjusted Poisson model (Dixon & Coles 1997).

    Computes P(home win), P(draw), P(away win) by summing joint Poisson
    probabilities over all scorelines up to max_goals x max_goals with the
    low-score correction parameter rho.

    Returns {"home_win": float, "draw": float, "away_win": float} summing
    to 1.0, or None when stats are insufficient.
    """
    def _f(d: dict, *keys) -> float | None:
        for k in keys:
            v = d.get(k)
            if v is not None:
                try:
                    f = float(v)
                    if f > 0:
                        return f
                except (TypeError, ValueError):
                    pass
        return None

    # ── Priority 1: Rolling 5-round form ─────────────────────────────────────
    avg_s_a = avg_c_a = avg_s_b = avg_c_b = None
    data_source = None

    if rolling_form and all(
        rolling_form.get(k) not in (None, "", 0)
        for k in ["home_scored_5r", "home_conceded_5r",
                   "away_scored_5r", "away_conceded_5r"]
    ):
        # Use actual rounds used (default to 5 if not specified)
        home_rounds = rolling_form.get("home_rounds_used", 5)
        away_rounds = rolling_form.get("away_rounds_used", 5)
        home_rounds = max(1, int(home_rounds)) if home_rounds else 5
        away_rounds = max(1, int(away_rounds)) if away_rounds else 5
        avg_s_a = rolling_form["home_scored_5r"] / home_rounds
        avg_c_a = rolling_form["home_conceded_5r"] / home_rounds
        avg_s_b = rolling_form["away_scored_5r"] / away_rounds
        avg_c_b = rolling_form["away_conceded_5r"] / away_rounds
        data_source = "rolling_5r"

    # ── Priority 2: Season Statistics endpoint ──────────────────────────────
    if avg_s_a is None and season_id and team_a_id and team_b_id:
        if season_id not in _season_stats_cache:
            _season_stats_cache[season_id] = get_season_team_stats(season_id)
        sdata = _season_stats_cache[season_id]
        ta = sdata.get(int(team_a_id))
        tb = sdata.get(int(team_b_id))
        if ta and tb:
            avg_s_a = ta.get("goals_scored_per_game")
            avg_c_a = ta.get("goals_conceded_per_game")
            avg_s_b = tb.get("goals_scored_per_game")
            avg_c_b = tb.get("goals_conceded_per_game")
            data_source = "season_stats"

    gs_a = _f(team_a_stats, "goals_scored")
    ga_a = _f(team_a_stats, "goals_conceded", "goals_against")
    pl_a = _f(team_a_stats, "total_matches", "played")
    gs_b = _f(team_b_stats, "goals_scored")
    ga_b = _f(team_b_stats, "goals_conceded", "goals_against")
    pl_b = _f(team_b_stats, "total_matches", "played")

    # ── Priority 3: Standings fallback ────────────────────────────────────────
    if avg_s_a is None or avg_c_a is None or avg_s_b is None or avg_c_b is None:
        if any(v is None for v in [gs_a, ga_a, pl_a, gs_b, ga_b, pl_b]):
            return None
        avg_s_a, avg_c_a = gs_a / pl_a, ga_a / pl_a  # type: ignore[operator]
        avg_s_b, avg_c_b = gs_b / pl_b, ga_b / pl_b  # type: ignore[operator]
        data_source = "standings"

    league_avg = ((avg_s_a + avg_s_b) / 2) or 0.01
    if league_avg < 0.01:
        return None

    atk_a = avg_s_a / league_avg
    def_a = avg_c_a / league_avg
    atk_b = avg_s_b / league_avg
    def_b = avg_c_b / league_avg

    # Expected goals: home team benefits from home_advantage multiplier
    # Use per-league coefficient if league_id provided, else fall back to param
    ha_coeff = _HOME_ADVANTAGE.get(league_id, _HOME_ADVANTAGE_DEFAULT) \
               if league_id else home_advantage
    ha = ha_coeff if is_home_a else 1.0 / ha_coeff
    lam = atk_a * def_b * ha         * league_avg  # team_a expected goals
    mu  = atk_b * def_a * (1.0 / ha) * league_avg  # team_b expected goals

    def _pois(k: int, lam_: float) -> float:
        return math.exp(-lam_) * (lam_ ** k) / math.factorial(k)

    # Dixon-Coles low-score correction τ(x, y)
    def _tau(x: int, y: int) -> float:
        if x == 0 and y == 0:
            return 1.0 - lam * mu * rho
        if x == 0 and y == 1:
            return 1.0 + lam * rho
        if x == 1 and y == 0:
            return 1.0 + mu  * rho
        if x == 1 and y == 1:
            return 1.0 - rho
        return 1.0

    home_win = draw = away_win = 0.0
    for i in range(max_goals + 1):
        pi = _pois(i, lam)
        for j in range(max_goals + 1):
            p = _tau(i, j) * pi * _pois(j, mu)
            if   i > j: home_win += p
            elif i == j: draw    += p
            else:        away_win += p

    total = home_win + draw + away_win
    if total <= 0:
        return None

    hw = max(0.05, min(0.90, home_win / total))
    dr = max(0.05, min(0.90, draw     / total))
    aw = max(0.05, min(0.90, away_win / total))

    # Normalise after capping, then apply the floor/ceiling again so the
    # returned values strictly respect the [0.05, 0.90] bounds.
    t2 = hw + dr + aw
    return {
        "home_win": max(0.05, min(0.90, round(hw / t2, 4))),
        "draw":     max(0.05, min(0.90, round(dr / t2, 4))),
        "away_win": max(0.05, min(0.90, round(aw / t2, 4))),
        "method": data_source,
    }


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

    # Top scorers (legacy key — kept for backwards compat)
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

    # ── NEW SECTIONS for improved Gemini reasoning ────────────────────────────

    # Confirmed lineups
    lineup = enriched.get("lineup") or {}
    team_a_starters: list[dict] = lineup.get("team_a_starters") or []
    team_b_starters: list[dict] = lineup.get("team_b_starters") or []
    lineup_confirmed = lineup.get("confirmed", False)

    if lineup_confirmed and (team_a_starters or team_b_starters):
        a_names = ", ".join(p["player_name"] for p in team_a_starters) or "Unknown"
        b_names = ", ".join(p["player_name"] for p in team_b_starters) or "Unknown"
        parts.append(
            f"CONFIRMED STARTING LINEUPS:\n"
            f"  {team_a_name} starting XI: {a_names}\n"
            f"  {team_b_name} starting XI: {b_names}"
        )
    else:
        parts.append(
            "CONFIRMED STARTING LINEUPS:\n"
            "  Lineups not yet confirmed for this match"
        )

    # Top scorers with names + lineup cross-reference
    scorers = enriched.get("topscorers_with_names") or []
    if scorers:
        starter_names_a = {p["player_name"].lower() for p in team_a_starters}
        starter_names_b = {p["player_name"].lower() for p in team_b_starters}
        scorer_lines = []
        for s in scorers:
            name  = s.get("player_name", "?")
            team  = s.get("team_name", "?")
            goals = s.get("goals", 0)
            rank  = s.get("rank", "?")
            flag  = ""
            if name.lower() in starter_names_a:
                flag = f" ← CONFIRMED STARTING for {team_a_name}"
            elif name.lower() in starter_names_b:
                flag = f" ← CONFIRMED STARTING for {team_b_name}"
            elif s.get("team_id") in (team_a_id, team_b_id):
                flag = " ← plays for one of today's teams (lineup TBC)"
            scorer_lines.append(f"  {rank}. {name} ({team}): {goals} goals{flag}")
        parts.append(
            "TOP SCORERS IN THIS LEAGUE (season):\n"
            + "\n".join(scorer_lines)
            + "\n  Instruction: if a top scorer is confirmed in the starting XI, "
            "weight their team's attacking threat higher in your prediction."
        )

    # Squad depth note — flags missing first-choice GK or captain for team_a
    squad_a: list[dict] = enriched.get("squad_a") or []
    if squad_a and lineup_confirmed and team_a_starters:
        starter_names_a_set = {p["player_name"].lower() for p in team_a_starters}
        key_absences = []
        for player in squad_a:
            pname = player.get("player_name", "")
            if pname.lower() in starter_names_a_set:
                continue  # player IS starting, not absent
            if player.get("position_id") == 24:  # 24 = goalkeeper
                key_absences.append(f"{pname} (GK)")
            elif player.get("captain"):
                key_absences.append(f"{pname} (captain)")
        if key_absences:
            absence_str = ", ".join(key_absences)
            parts.append(
                f"SQUAD DEPTH NOTE ({team_a_name}):\n"
                f"  Key player(s) absent from starting XI: {absence_str}\n"
                f"  Instruction: a missing captain or first-choice goalkeeper "
                f"significantly affects {team_a_name}'s prediction confidence — "
                f"lower their defensive/leadership rating accordingly."
            )

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

    # Dixon-Coles probabilities — computed from standings data, never from Gemini
    dc_probs: dict | None = None
    if enriched_data:
        _season_id = (enriched_data or {}).get("season_id")
        dc_probs = dixon_coles_probability(
            enriched_data.get("team_a_stats") or {},
            enriched_data.get("team_b_stats") or {},
            is_home_a=True,  # team_a_id is always the home team (see fixture_prediction)
            season_id=_season_id,
            team_a_id=team_a_id,
            team_b_id=team_b_id,
        )

    if enriched_data:
        enriched_section = _build_enriched_section(
            team_a_name, team_b_name, team_a_id, team_b_id, enriched_data
        )
        today_str = _date.today().isoformat()
        grounding_instruction = (
            f"REAL-TIME NEWS INSTRUCTION (Google Search):\n"
            f"Search for: \"{team_a_name} vs {team_b_name} injury news team news lineup {today_str}\"\n"
            f"If you find relevant injury reports, lineup hints, or manager press-conference\n"
            f"quotes, include them in this format inside your response:\n\n"
            f"REAL-TIME TEAM NEWS (from Google Search):\n"
            f"- [finding about {team_a_name} injuries or lineup hints]\n"
            f"- [finding about {team_b_name} injuries or lineup hints]\n"
            f"- [manager quote or press-conference note if found]\n\n"
            f"Weave these findings into the Reasoning sentences alongside the statistical data.\n"
            f"If no relevant real-time information is found, proceed with the data above only."
        )
        data_block = f"{h2h_section}\n\n{enriched_section}\n\n{grounding_instruction}"
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

    _search_tools = [types.Tool(google_search=types.GoogleSearch())]

    try:
        # Attempt grounded call so Gemini can retrieve real-time injury/team news.
        # If grounding is unavailable (plan restriction, SDK mismatch, etc.) fall back
        # to a plain call so the prediction always completes.
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                tools=_search_tools,
            )
        except Exception:
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

        # Win-probability split — Dixon-Coles when stats available, else confidence fallback
        if dc_probs:
            result_data["home_win_probability"] = dc_probs["home_win"]
            result_data["draw_probability"]     = dc_probs["draw"]
            result_data["away_win_probability"] = dc_probs["away_win"]
            result_data["probability_method"]   = "dixon-coles"
        else:
            # Confidence-label fallback: assign probabilities based on predicted winner
            _fb: dict[str, tuple[float, float, float]] = {
                "high":   (0.72, 0.18, 0.10),
                "medium": (0.52, 0.23, 0.25),
                "low":    (0.38, 0.28, 0.34),
            }
            conf_key = parsed.get("Confidence", "low").lower()
            w_p, dr_p, l_p = _fb.get(conf_key, _fb["low"])
            winner_is_home = parsed.get("Winner", "").lower() == team_a_name.lower()
            result_data["home_win_probability"] = w_p if winner_is_home else l_p
            result_data["draw_probability"]     = dr_p
            result_data["away_win_probability"] = l_p if winner_is_home else w_p
            result_data["probability_method"]   = "confidence-estimate"

        return {"status": "success", "data": result_data}
    except Exception as e:
        return {"status": "reasoning_failed", "message": str(e)}
