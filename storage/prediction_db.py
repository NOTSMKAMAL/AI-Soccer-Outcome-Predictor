"""SQLite prediction-history store — the system of record.

Holds every generated prediction, the resolved match outcome, and market
snapshots that drive edge / Closing Line Value. engine/tracking.py reads and
writes through here, keeping its flat-row shape and public API.

Schema (3 tables):
  predictions(id, match_id, competition, home_team, away_team, prediction_date,
              match_date, stage, home_prob, draw_prob, away_prob,
              predicted_winner, confidence, risk_level, probability_method)
      UNIQUE(match_id, probability_method) — re-predicting upserts in place.
  outcomes(prediction_id PK/FK, actual_winner, correct, final_result,
           resolved_at, pnl_simulation)
  market_snapshots(id, prediction_id FK, captured_at, market_prob, edge,
                   value_signal, is_closing)
      Opening snapshot (is_closing=0) at prediction time; closing snapshot
      (is_closing=1) near kickoff. The pair yields CLV.

Design: stdlib sqlite3 only, one short-lived connection per call (safe across
FastAPI worker threads), a process lock around writes. Never raises to callers
that don't want it — engine/tracking.py wraps logging best-effort.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)
# Override with PREDICTIONS_DB_PATH when the default location is not writable or
# not persistent (e.g. a hosted container with an attached disk elsewhere).
DB_PATH = os.getenv("PREDICTIONS_DB_PATH") or os.path.join(
    _PROJECT_ROOT, "scripts", "data", "predictions.db"
)

_write_lock = threading.Lock()
_initialized = False

_SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id          TEXT NOT NULL,
    competition       TEXT,
    home_team         TEXT,
    away_team         TEXT,
    prediction_date   TEXT,
    match_date        TEXT,
    stage             TEXT,
    home_prob         REAL,
    draw_prob         REAL,
    away_prob         REAL,
    raw_home_prob     REAL,
    raw_draw_prob     REAL,
    raw_away_prob     REAL,
    predicted_winner  TEXT,
    confidence        TEXT,
    risk_level        TEXT,
    probability_method TEXT,
    UNIQUE(match_id, probability_method)
);
CREATE TABLE IF NOT EXISTS outcomes (
    prediction_id   INTEGER PRIMARY KEY REFERENCES predictions(id) ON DELETE CASCADE,
    actual_winner   TEXT,
    correct         INTEGER,
    final_result    TEXT,
    resolved_at     TEXT,
    pnl_simulation  REAL
);
CREATE TABLE IF NOT EXISTS market_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id   INTEGER NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    captured_at     TEXT,
    market_prob     REAL,
    edge            REAL,
    value_signal    TEXT,
    is_closing      INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_pred_competition ON predictions(competition);
CREATE INDEX IF NOT EXISTS idx_snap_pred ON market_snapshots(prediction_id);
"""


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables if missing (idempotent) and migrate older schemas."""
    global _initialized
    with _write_lock:
        conn = _connect()
        try:
            conn.executescript(_SCHEMA)
            # Additive migration: raw_* probability columns (Priority 4) on DBs
            # created before calibration existed.
            have = {r[1] for r in conn.execute("PRAGMA table_info(predictions)")}
            for col in ("raw_home_prob", "raw_draw_prob", "raw_away_prob"):
                if col not in have:
                    conn.execute(f"ALTER TABLE predictions ADD COLUMN {col} REAL")
            conn.commit()
        finally:
            conn.close()
        _initialized = True


def _ensure() -> None:
    if not _initialized:
        init_db()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Writes ────────────────────────────────────────────────────────────────────

def upsert_prediction(row: dict) -> int | None:
    """Insert or update a prediction from engine/tracking.py's flat-row dict.

    Dedupes on (match_id, probability_method). Records an opening market snapshot
    when market fields are present. Preserves any existing outcome/snapshots.
    Returns the prediction id, or None when there's no usable match_id.
    """
    _ensure()
    match_id = str(row.get("match_id") or "")
    if not match_id:
        return None
    method = row.get("probability_method")

    with _write_lock:
        conn = _connect()
        try:
            cur = conn.execute(
                """
                INSERT INTO predictions
                    (match_id, competition, home_team, away_team, prediction_date,
                     match_date, stage, home_prob, draw_prob, away_prob,
                     raw_home_prob, raw_draw_prob, raw_away_prob,
                     predicted_winner, confidence, risk_level, probability_method)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(match_id, probability_method) DO UPDATE SET
                    competition=excluded.competition,
                    home_team=excluded.home_team,
                    away_team=excluded.away_team,
                    prediction_date=excluded.prediction_date,
                    match_date=excluded.match_date,
                    stage=excluded.stage,
                    home_prob=excluded.home_prob,
                    draw_prob=excluded.draw_prob,
                    away_prob=excluded.away_prob,
                    raw_home_prob=excluded.raw_home_prob,
                    raw_draw_prob=excluded.raw_draw_prob,
                    raw_away_prob=excluded.raw_away_prob,
                    predicted_winner=excluded.predicted_winner,
                    confidence=excluded.confidence,
                    risk_level=excluded.risk_level
                """,
                (
                    match_id, row.get("competition"), row.get("home_team"),
                    row.get("away_team"), row.get("logged_at") or _now(),
                    row.get("match_date"), row.get("stage"),
                    row.get("home_probability"), row.get("draw_probability"),
                    row.get("away_probability"),
                    row.get("raw_home_probability"), row.get("raw_draw_probability"),
                    row.get("raw_away_probability"),
                    row.get("winner") or row.get("prediction"),
                    row.get("confidence"), row.get("risk_level"), method,
                ),
            )
            pred = conn.execute(
                "SELECT id FROM predictions WHERE match_id=? AND probability_method IS ?",
                (match_id, method),
            ).fetchone()
            pid = pred["id"] if pred else cur.lastrowid

            # Opening market snapshot (idempotent: replace the existing opening row).
            market_prob = row.get("market_probability")
            if market_prob is not None or row.get("edge") is not None or row.get("signal"):
                conn.execute(
                    "DELETE FROM market_snapshots WHERE prediction_id=? AND is_closing=0",
                    (pid,),
                )
                conn.execute(
                    """INSERT INTO market_snapshots
                       (prediction_id, captured_at, market_prob, edge, value_signal, is_closing)
                       VALUES (?,?,?,?,?,0)""",
                    (pid, _now(), market_prob, row.get("edge"), row.get("signal")),
                )
            conn.commit()
            return pid
        finally:
            conn.close()


def record_closing_snapshot(match_id: str, market_prob: float, value_signal: str | None = None,
                            edge: float | None = None) -> int:
    """Store a closing market snapshot for every prediction of a match (drives CLV)."""
    _ensure()
    with _write_lock:
        conn = _connect()
        try:
            ids = [r["id"] for r in conn.execute(
                "SELECT id FROM predictions WHERE match_id=?", (str(match_id),)).fetchall()]
            for pid in ids:
                conn.execute(
                    "DELETE FROM market_snapshots WHERE prediction_id=? AND is_closing=1", (pid,))
                conn.execute(
                    """INSERT INTO market_snapshots
                       (prediction_id, captured_at, market_prob, edge, value_signal, is_closing)
                       VALUES (?,?,?,?,?,1)""",
                    (pid, _now(), market_prob, edge, value_signal))
            conn.commit()
            return len(ids)
        finally:
            conn.close()


def resolve_outcomes(by_id: dict[str, dict]) -> int:
    """Fill outcomes for finished matches.

    by_id: {match_id: {"outcome": "home_win"|"draw"|"away_win", "final_result": "2-1"}}
    Computes `correct` from the stored predicted winner and a flat-stake
    `pnl_simulation` when an opening market price exists. Returns rows newly resolved.
    """
    _ensure()
    resolved = 0
    with _write_lock:
        conn = _connect()
        try:
            for match_id, info in (by_id or {}).items():
                outcome = info.get("outcome")
                if outcome not in ("home_win", "draw", "away_win"):
                    continue
                preds = conn.execute(
                    "SELECT * FROM predictions WHERE match_id=?", (str(match_id),)).fetchall()
                for p in preds:
                    exists = conn.execute(
                        "SELECT 1 FROM outcomes WHERE prediction_id=?", (p["id"],)).fetchone()
                    if exists:
                        continue
                    side = _winner_side(p)
                    correct = 1 if side == outcome else 0
                    pnl = _pnl(conn, p["id"], side, outcome)
                    conn.execute(
                        """INSERT INTO outcomes
                           (prediction_id, actual_winner, correct, final_result, resolved_at, pnl_simulation)
                           VALUES (?,?,?,?,?,?)""",
                        (p["id"], outcome, correct, info.get("final_result"), _now(), pnl))
                    resolved += 1
            conn.commit()
        finally:
            conn.close()
    return resolved


def _winner_side(pred: sqlite3.Row) -> str:
    winner = pred["predicted_winner"]
    if winner == pred["home_team"]:
        return "home_win"
    if winner == pred["away_team"]:
        return "away_win"
    return "draw"


def _pnl(conn: sqlite3.Connection, pid: int, side: str, outcome: str) -> float | None:
    snap = conn.execute(
        "SELECT market_prob FROM market_snapshots WHERE prediction_id=? AND is_closing=0",
        (pid,)).fetchone()
    if not snap or not snap["market_prob"]:
        return None
    mkt = snap["market_prob"]
    if not (0 < mkt < 1):
        return None
    return round((1.0 / mkt - 1.0) if side == outcome else -1.0, 4)


# ── Reads ─────────────────────────────────────────────────────────────────────

def read_rows(competition: str | None = None) -> list[dict]:
    """Return flat prediction rows (engine/tracking.py's shape), optionally filtered.

    Joins the opening/closing market snapshots and the outcome into one dict per
    prediction so the existing calibration/betting reporting consumes them as-is.
    """
    _ensure()
    conn = _connect()
    try:
        sql = "SELECT * FROM predictions"
        params: tuple = ()
        if competition:
            sql += " WHERE competition=?"
            params = (competition,)
        preds = conn.execute(sql, params).fetchall()

        rows: list[dict] = []
        for p in preds:
            opening = conn.execute(
                "SELECT market_prob, edge, value_signal FROM market_snapshots "
                "WHERE prediction_id=? AND is_closing=0 ORDER BY id DESC LIMIT 1",
                (p["id"],)).fetchone()
            closing = conn.execute(
                "SELECT market_prob FROM market_snapshots "
                "WHERE prediction_id=? AND is_closing=1 ORDER BY id DESC LIMIT 1",
                (p["id"],)).fetchone()
            outcome = conn.execute(
                "SELECT actual_winner, final_result FROM outcomes WHERE prediction_id=?",
                (p["id"],)).fetchone()
            rows.append({
                "match_id": p["match_id"],
                "competition": p["competition"],
                "logged_at": p["prediction_date"],
                "match_date": p["match_date"],
                "stage": p["stage"],
                "home_team": p["home_team"],
                "away_team": p["away_team"],
                "winner": p["predicted_winner"],
                "prediction": p["predicted_winner"],
                "confidence": p["confidence"],
                "risk_level": p["risk_level"],
                "probability_method": p["probability_method"],
                "home_probability": p["home_prob"],
                "draw_probability": p["draw_prob"],
                "away_probability": p["away_prob"],
                "raw_home_probability": p["raw_home_prob"],
                "raw_draw_probability": p["raw_draw_prob"],
                "raw_away_probability": p["raw_away_prob"],
                "model_probability": (opening["market_prob"] if opening else None),
                "market_probability": (opening["market_prob"] if opening else None),
                "edge": (opening["edge"] if opening else None),
                "signal": (opening["value_signal"] if opening else None),
                "closing_market_probability": (closing["market_prob"] if closing else None),
                "result": (outcome["actual_winner"] if outcome else None),
                "final_result": (outcome["final_result"] if outcome else None),
            })
        return rows
    finally:
        conn.close()
