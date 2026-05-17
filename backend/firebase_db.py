from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from firebase_admin import firestore
from backend.firebase_config import _get_app

_COLLECTION = "predictions"


def _db():
    """Return a Firestore client, or None if Firebase is not configured."""
    app = _get_app()
    if app is None:
        return None
    try:
        return firestore.client(app=app)
    except Exception:
        return None


def save_prediction(user_id: str, prediction_data: dict[str, Any]) -> str | None:
    """
    Persist a prediction for a user.

    Returns the document ID on success, or None if Firebase is unavailable.

    Expected keys in prediction_data:
        fixture_id, home_team, away_team, predicted_winner,
        confidence, reasoning, match_datetime (ISO string or datetime)
    """
    db = _db()
    if db is None:
        return None

    match_dt = prediction_data.get("match_datetime")
    if isinstance(match_dt, str):
        try:
            match_dt = datetime.fromisoformat(match_dt)
        except ValueError:
            match_dt = None

    doc_id = str(uuid.uuid4())
    doc = {
        "user_id": user_id,
        "fixture_id": prediction_data.get("fixture_id"),
        "home_team": prediction_data.get("home_team", ""),
        "away_team": prediction_data.get("away_team", ""),
        "predicted_winner": prediction_data.get("predicted_winner", ""),
        "confidence": prediction_data.get("confidence", 0),
        "reasoning": prediction_data.get("reasoning", ""),
        "match_datetime": match_dt,
        "created_at": datetime.now(tz=timezone.utc),
    }

    try:
        db.collection(_COLLECTION).document(doc_id).set(doc)
        return doc_id
    except Exception:
        return None


def get_user_predictions(user_id: str) -> list[dict[str, Any]]:
    """
    Retrieve all predictions for a user, ordered newest-first.

    Returns an empty list if Firebase is unavailable or no predictions exist.
    """
    db = _db()
    if db is None:
        return []

    try:
        docs = (
            db.collection(_COLLECTION)
            .where("user_id", "==", user_id)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .stream()
        )
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            # Convert Firestore timestamps to ISO strings for JSON serialisation
            for field in ("created_at", "match_datetime"):
                val = data.get(field)
                if hasattr(val, "isoformat"):
                    data[field] = val.isoformat()
            results.append(data)
        return results
    except Exception:
        return []


def delete_prediction(prediction_id: str) -> bool:
    """
    Delete a prediction document by ID.

    Returns True on success, False if Firebase is unavailable or the
    document does not exist.
    """
    db = _db()
    if db is None:
        return False

    try:
        ref = db.collection(_COLLECTION).document(prediction_id)
        if not ref.get().exists:
            return False
        ref.delete()
        return True
    except Exception:
        return False
