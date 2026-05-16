from typing import Any, TypedDict
from langgraph.graph import StateGraph, END
from backend.soccer_api import SoccerApiClient
from backend.supabase_db import (
    read_cached_prediction,
    write_prediction,
    read_cached_team_stats,
    write_team_stats,
)
from backend.predictor import predict
from backend.config import GEMINI_API_KEY

soccer_client = SoccerApiClient()


class AgentState(TypedDict):
    team_a_id: int
    team_b_id: int
    team_a_name: str
    team_b_name: str
    stats_a: dict[str, float]
    stats_b: dict[str, float]
    prediction: dict[str, Any]
    cached: bool
    error: str


def fetch_team_stats(state: AgentState) -> AgentState:
    team_a_id = state["team_a_id"]
    team_b_id = state["team_b_id"]

    stats_a = read_cached_team_stats(team_a_id)
    if stats_a is None:
        stats_a = soccer_client.get_team_stats(team_a_id)
        write_team_stats(team_a_id, stats_a)

    stats_b = read_cached_team_stats(team_b_id)
    if stats_b is None:
        stats_b = soccer_client.get_team_stats(team_b_id)
        write_team_stats(team_b_id, stats_b)

    return {**state, "stats_a": stats_a, "stats_b": stats_b}


def compute_prediction(state: AgentState) -> AgentState:
    result = predict(
        state["team_a_id"],
        state["team_a_name"],
        state["team_b_id"],
        state["team_b_name"],
        state["stats_a"],
        state["stats_b"],
    )
    return {**state, "prediction": result}


def enrich_with_llm(state: AgentState) -> AgentState:
    if not GEMINI_API_KEY:
        return state
    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-pro")

        pred = state["prediction"]
        prompt = (
            f"You are a soccer analyst. Two national teams are competing: "
            f"{pred['teams']['team_a']['name']} vs {pred['teams']['team_b']['name']}.\n\n"
            f"Statistics:\n"
            f"- Attack: {pred['comparison']['attack']}\n"
            f"- Defense: {pred['comparison']['defense']}\n"
            f"- Recent form (0-5 scale): {pred['comparison']['recent_form']}\n\n"
            f"The statistical model predicts {pred['winner']} wins with {pred['confidence']}% confidence.\n\n"
            f"Write a 2-3 sentence expert analysis explaining why {pred['winner']} is predicted to win. "
            f"Be specific about the stats. Do not use bullet points."
        )

        response = model.generate_content(prompt)
        llm_reasoning = response.text.strip()
        updated_pred = {**pred, "reasoning": llm_reasoning}
        return {**state, "prediction": updated_pred}
    except Exception:
        return state


def cache_result(state: AgentState) -> AgentState:
    pred = state["prediction"]
    write_prediction(
        team_a_id=state["team_a_id"],
        team_b_id=state["team_b_id"],
        winner=pred["winner"],
        confidence=pred["confidence"],
        reasoning=pred["reasoning"],
        comparison=pred["comparison"],
    )
    return state


def _build_graph() -> Any:
    graph = StateGraph(AgentState)
    graph.add_node("fetch_team_stats", fetch_team_stats)
    graph.add_node("compute_prediction", compute_prediction)
    graph.add_node("enrich_with_llm", enrich_with_llm)
    graph.add_node("cache_result", cache_result)

    graph.set_entry_point("fetch_team_stats")
    graph.add_edge("fetch_team_stats", "compute_prediction")
    graph.add_edge("compute_prediction", "enrich_with_llm")
    graph.add_edge("enrich_with_llm", "cache_result")
    graph.add_edge("cache_result", END)

    return graph.compile()


_compiled_graph = _build_graph()


def run_prediction_agent(team_a_id: int, team_b_id: int) -> dict[str, Any]:
    cached = read_cached_prediction(team_a_id, team_b_id)
    if cached:
        return {
            "teams": {
                "team_a": {"id": cached["team_a_id"], "name": soccer_client.get_team_name(cached["team_a_id"])},
                "team_b": {"id": cached["team_b_id"], "name": soccer_client.get_team_name(cached["team_b_id"])},
            },
            "winner": cached["winner"],
            "confidence": cached["confidence"],
            "reasoning": cached["reasoning"],
            "comparison": cached["comparison"],
        }

    team_a_name = soccer_client.get_team_name(team_a_id)
    team_b_name = soccer_client.get_team_name(team_b_id)

    initial_state: AgentState = {
        "team_a_id": team_a_id,
        "team_b_id": team_b_id,
        "team_a_name": team_a_name,
        "team_b_name": team_b_name,
        "stats_a": {},
        "stats_b": {},
        "prediction": {},
        "cached": False,
        "error": "",
    }

    final_state = _compiled_graph.invoke(initial_state)
    return final_state["prediction"]
