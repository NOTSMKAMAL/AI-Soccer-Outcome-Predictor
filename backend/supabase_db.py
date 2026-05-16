from typing import Any
from datetime import datetime, timezone

from backend.config import SUPABASE_URL, SUPABASE_KEY

_supabase_client = None


def _get_client():
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        from supabase import create_client
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return _supabase_client
    except Exception:
        return None


def read_cached_prediction(team_a_id: int, team_b_id: int) -> dict[str, Any] | None:
    client = _get_client()
    if client is None:
        return None
    try:
        result = (
            client.table("predictions")
            .select("*")
            .eq("team_a_id", team_a_id)
            .eq("team_b_id", team_b_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data
        if not rows:
            return None
        row = rows[0]
        created = datetime.fromisoformat(row["created_at"]).replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
        if age_hours > 24:
            return None
        return row
    except Exception:
        return None


def write_prediction(
    team_a_id: int,
    team_b_id: int,
    winner: str,
    confidence: int,
    reasoning: str,
    comparison: dict[str, Any],
) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.table("predictions").insert(
            {
                "team_a_id": team_a_id,
                "team_b_id": team_b_id,
                "winner": winner,
                "confidence": confidence,
                "reasoning": reasoning,
                "comparison": comparison,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
    except Exception:
        pass


def read_cached_team_stats(team_id: int) -> dict[str, float] | None:
    client = _get_client()
    if client is None:
        return None
    try:
        result = (
            client.table("team_stats")
            .select("*")
            .eq("team_id", team_id)
            .order("fetched_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data
        if not rows:
            return None
        row = rows[0]
        fetched = datetime.fromisoformat(row["fetched_at"]).replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - fetched).total_seconds() / 3600
        if age_hours > 6:
            return None
        return {"attack": row["attack"], "defense": row["defense"], "recent_form": row["recent_form"]}
    except Exception:
        return None


def write_team_stats(team_id: int, stats: dict[str, float]) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.table("team_stats").insert(
            {
                "team_id": team_id,
                "attack": stats["attack"],
                "defense": stats["defense"],
                "recent_form": stats["recent_form"],
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
    except Exception:
        pass
