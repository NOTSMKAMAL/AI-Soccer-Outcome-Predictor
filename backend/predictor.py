from typing import Any


WEIGHTS = {"attack": 0.40, "defense": 0.35, "recent_form": 0.25}


def compute_score(stats: dict[str, float]) -> float:
    return (
        stats["attack"] * WEIGHTS["attack"]
        + stats["defense"] * WEIGHTS["defense"]
        + stats["recent_form"] * WEIGHTS["recent_form"] * 2
    )


def compute_confidence(score_a: float, score_b: float) -> int:
    total = score_a + score_b
    if total == 0:
        return 50
    dominant = max(score_a, score_b)
    raw = (dominant / total) * 100
    return max(50, min(99, round(raw)))


def build_reasoning(
    team_a_name: str,
    team_b_name: str,
    stats_a: dict[str, float],
    stats_b: dict[str, float],
    winner: str,
    confidence: int,
) -> str:
    loser = team_b_name if winner == team_a_name else team_a_name
    loser_stats = stats_b if winner == team_a_name else stats_a
    winner_stats = stats_a if winner == team_a_name else stats_b

    form_diff = winner_stats["recent_form"] - loser_stats["recent_form"]
    form_wins_winner = round(winner_stats["recent_form"] * 5 / 5)
    form_wins_loser = round(loser_stats["recent_form"] * 5 / 5)

    attack_edge = "superior" if winner_stats["attack"] > loser_stats["attack"] else "comparable"
    defense_edge = "stronger" if winner_stats["defense"] > loser_stats["defense"] else "slightly weaker"

    return (
        f"{winner} shows {attack_edge} recent form with {form_wins_winner} wins in last 5 matches "
        f"compared to {loser}'s {form_wins_loser} wins. "
        f"Attack strength favors {winner} ({winner_stats['attack']}/10 vs {loser_stats['attack']}/10), "
        f"though {loser} has a {'slight ' if abs(winner_stats['defense'] - loser_stats['defense']) < 0.5 else ''}"
        f"defensive {'edge' if loser_stats['defense'] > winner_stats['defense'] else 'weakness'} "
        f"({loser_stats['defense']}/10 vs {winner_stats['defense']}/10). "
        f"Overall confidence in {winner}: {confidence}%."
    )


def predict(
    team_a_id: int,
    team_a_name: str,
    team_b_id: int,
    team_b_name: str,
    stats_a: dict[str, float],
    stats_b: dict[str, float],
) -> dict[str, Any]:
    score_a = compute_score(stats_a)
    score_b = compute_score(stats_b)

    winner_name = team_a_name if score_a >= score_b else team_b_name
    winner_id = team_a_id if score_a >= score_b else team_b_id
    confidence = compute_confidence(score_a, score_b)

    reasoning = build_reasoning(
        team_a_name, team_b_name, stats_a, stats_b, winner_name, confidence
    )

    return {
        "teams": {
            "team_a": {"id": team_a_id, "name": team_a_name},
            "team_b": {"id": team_b_id, "name": team_b_name},
        },
        "winner": winner_name,
        "winner_id": winner_id,
        "confidence": confidence,
        "reasoning": reasoning,
        "comparison": {
            "attack": {
                team_a_name.lower(): stats_a["attack"],
                team_b_name.lower(): stats_b["attack"],
            },
            "defense": {
                team_a_name.lower(): stats_a["defense"],
                team_b_name.lower(): stats_b["defense"],
            },
            "recent_form": {
                team_a_name.lower(): stats_a["recent_form"],
                team_b_name.lower(): stats_b["recent_form"],
            },
        },
    }
