"""Prediction tracking — the honest-accuracy record for the app.

Every generated prediction is upserted into the SQLite store
(`storage/prediction_db.py`). A later resolution pass fills in the actual result
from finished fixtures, after which we can compute honest accuracy / Brier /
log-loss / calibration and ROI / win-rate / average-edge / CLV by reusing the
shared scoring in `scripts/calibration.py`.

Design notes:
- Logging never raises and never blocks a prediction (best-effort write).
- One row per (match_id, probability_method) — re-predicting the same match with
  the same model variant overwrites in-place so the log doesn't accumulate dupes.
- Market fields (edge / signal / closing price) stay None unless a market
  probability is supplied, so the betting report is simply empty without one.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone

from storage import prediction_db

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)


def _read_all(competition: str | None = None) -> list[dict]:
    """All prediction rows (flat shape) from the SQLite system of record."""
    return prediction_db.read_rows(competition)


def _default_competition(match_context: dict) -> str:
    """Best-effort competition label for a logged prediction.

    Callers pass the competition name/code explicitly via
    match_context['competition']; anything else is recorded as UNKNOWN.
    """
    explicit = match_context.get("competition")
    return str(explicit) if explicit else "UNKNOWN"


def log_prediction(match_context: dict, home: str, away: str, data: dict) -> None:
    """Upsert a prediction into the SQLite store. Best-effort; swallows all errors."""
    try:
        ma = data.get("market_analysis") or {}
        row = {
            "match_id": str(match_context.get("match_id") or match_context.get("id") or ""),
            "competition": _default_competition(match_context),
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "match_date": match_context.get("match_date"),
            "stage": match_context.get("stage"),
            "home_team": home,
            "away_team": away,
            "winner": data.get("winner"),
            "confidence": data.get("confidence"),
            "risk_level": data.get("risk_level"),
            "probability_method": data.get("probability_method"),
            "home_probability": data.get("home_win_probability"),
            "draw_probability": data.get("draw_probability"),
            "away_probability": data.get("away_win_probability"),
            # Raw (pre-calibration) probs kept so calibration can be retrained on raw.
            "raw_home_probability": data.get("raw_home_win_probability"),
            "raw_draw_probability": data.get("raw_draw_probability"),
            "raw_away_probability": data.get("raw_away_win_probability"),
            # Betting — populated from a market analysis payload when present.
            "model_probability": ma.get("model_probability"),
            "market_probability": ma.get("market_implied_probability"),
            "edge": ma.get("edge"),
            "signal": ma.get("signal"),
        }
        if not row["match_id"]:
            return  # without a stable id we can't dedupe or resolve
        prediction_db.upsert_prediction(row)
    except Exception:
        pass


def resolve_results(finished_matches: list[dict]) -> int:
    """Fill outcomes for logged predictions from finished fixtures.

    `finished_matches`: normalized fixture dicts with a numeric score.
    Returns the number of predictions newly resolved.
    """
    by_id: dict[str, dict] = {}
    for m in finished_matches or []:
        score = m.get("score") or {}
        h, a = score.get("home"), score.get("away")
        if h is None or a is None:
            continue
        outcome = "home_win" if h > a else "away_win" if a > h else "draw"
        by_id[str(m.get("id"))] = {"outcome": outcome, "final_result": f"{h}-{a}"}
    try:
        return prediction_db.resolve_outcomes(by_id)
    except Exception:
        return 0


# ── Metrics (calibration + betting) ───────────────────────────────────────────

def _resolved_rows(competition: str | None = None) -> list[dict]:
    return [r for r in _read_all(competition) if r.get("result") in ("home_win", "draw", "away_win")]


def _records_from_rows(rows: list[dict]) -> list[dict]:
    """Calibration-shaped records ({probs, predicted, actual, correct}) from stored rows."""
    records = []
    for r in rows:
        probs = {"home_win": r.get("home_probability") or 1 / 3,
                 "draw": r.get("draw_probability") or 1 / 3,
                 "away_win": r.get("away_probability") or 1 / 3}
        predicted = max(probs, key=probs.get)
        records.append({"probs": probs, "predicted": predicted,
                        "actual": r["result"], "correct": predicted == r["result"]})
    return records


def _calibration_fns():
    """Import the shared scoring helpers from scripts/calibration (path-robust)."""
    import sys
    _scripts = os.path.join(_PROJECT_ROOT, "scripts")
    if _scripts not in sys.path:
        sys.path.insert(0, _scripts)
    from calibration import brier_and_logloss, top_label_reliability, multiclass_ece
    return brier_and_logloss, top_label_reliability, multiclass_ece


def _score(records: list[dict]) -> dict:
    """Accuracy + Brier + log-loss + ECE for a set of calibration records."""
    n = len(records)
    if n == 0:
        return {"n": 0}
    acc = sum(1 for r in records if r["correct"]) / n
    out = {"n": n, "accuracy": round(acc, 4)}
    try:
        brier_and_logloss, top_label_reliability, multiclass_ece = _calibration_fns()
        brier, logloss = brier_and_logloss(records)
        _, ece = top_label_reliability(records, n_bins=10)
        out.update({"brier_score": round(brier, 4), "log_loss": round(logloss, 4),
                    "reliability_ece": round(ece, 4),
                    "multiclass_ece": round(multiclass_ece(records, n_bins=10), 4)})
    except Exception:
        out["note"] = "calibration module unavailable; accuracy only"
    return out


def _bet_rows(competition: str | None = None) -> list[dict]:
    """Resolved rows that carried an actionable value signal."""
    return [r for r in _resolved_rows(competition) if r.get("edge") is not None
            and r.get("signal") in ("Good Value", "Lean")]


def _bet_metrics(rows: list[dict]) -> dict:
    """ROI / win-rate / avg-edge / CLV over a set of value-bet rows."""
    n = len(rows)
    if n == 0:
        return {"bets": 0}
    wins = pnl = edge_sum = 0.0
    clv_vals: list[float] = []
    for r in rows:
        # Bet is on the predicted WINNER's side; map team name -> outcome label.
        winner = r.get("winner") or r.get("prediction")
        side = ("home_win" if winner == r.get("home_team")
                else "away_win" if winner == r.get("away_team") else "draw")
        won = side == r.get("result")
        wins += 1 if won else 0
        mkt = r.get("market_probability")
        if mkt and 0 < mkt < 1:
            pnl += (1.0 / mkt - 1.0) if won else -1.0  # flat 1u at market odds
        edge_sum += r.get("edge") or 0.0
        close = r.get("closing_market_probability")
        if close is not None and mkt is not None:
            clv_vals.append(mkt - close)
    return {
        "bets": n,
        "win_rate": round(wins / n, 4),
        "roi": round(pnl / n, 4),
        "average_edge_pts": round(edge_sum / n, 2),
        "clv_samples": len(clv_vals),
        "average_clv": round(sum(clv_vals) / len(clv_vals), 4) if clv_vals else None,
    }


def calibration_report(competition: str | None = None) -> dict:
    """Accuracy / Brier / log-loss / reliability over resolved predictions."""
    rows = _resolved_rows(competition)
    base = {"generated": date.today().isoformat(), "competition": competition or "all",
            "resolved_predictions": len(rows)}
    if not rows:
        return {**base, "message": "No resolved predictions yet — metrics appear after matches finish."}
    return {**base, **{k: v for k, v in _score(_records_from_rows(rows)).items() if k != "n"}}


def betting_report(competition: str | None = None) -> dict:
    """ROI / win-rate / avg-edge / CLV over resolved value bets."""
    rows = _bet_rows(competition)
    base = {"generated": date.today().isoformat(), "competition": competition or "all",
            "qualifying_bets": len(rows)}
    if not rows:
        return {**base, "message": "No resolved value bets yet (needs finished matches with a market edge)."}
    m = _bet_metrics(rows)
    return {**base, **m,
            "clv_note": None if m.get("clv_samples") else "No closing prices captured — CLV needs closing odds."}


def _period_key(row: dict) -> str:
    """Bucket a row by its match date (YYYY-MM-DD); falls back to log date."""
    d = (row.get("match_date") or row.get("logged_at") or "")[:10]
    return d or "unknown"


def analytics_report(competition: str | None = None) -> dict:
    """Combined dashboard payload: summary + reliability bins + over-time series.

    Returns metrics over ALL resolved predictions plus a chronological series (one
    point per match day) with per-period and CUMULATIVE accuracy / Brier / log-loss
    / ROI / CLV — i.e. the trends the calibration dashboard charts. Always safe.
    """
    resolved = sorted(_resolved_rows(competition), key=_period_key)
    bet_rows = _bet_rows(competition)
    base = {
        "generated": date.today().isoformat(),
        "competition": competition or "all",
        "resolved_predictions": len(resolved),
        "total_logged": len(_read_all(competition)),
        "qualifying_bets": len(bet_rows),
    }
    if not resolved:
        return {**base, "summary": None, "reliability": [], "over_time": [],
                "message": "No resolved predictions yet — metrics fill in as tracked matches finish."}

    summary = _score(_records_from_rows(resolved))
    summary.update({k: v for k, v in _bet_metrics(bet_rows).items()})

    # Confidence distribution: count + accuracy per confidence band.
    conf_dist = []
    for band in ("low", "medium", "high"):
        recs = _records_from_rows(
            [r for r in resolved if (r.get("confidence") or "").lower() == band])
        n = len(recs)
        acc = (sum(1 for r in recs if r["correct"]) / n) if n else None
        conf_dist.append({"band": band, "n": n,
                          "accuracy": round(acc, 4) if acc is not None else None})

    # Reliability bins for the diagram.
    reliability: list[dict] = []
    try:
        _, top_label_reliability, _ = _calibration_fns()
        bins, _ece = top_label_reliability(_records_from_rows(resolved), n_bins=10)
        for b in bins:
            if not b.get("count"):
                continue
            reliability.append({
                "lo": round(b["lo"], 2), "hi": round(b["hi"], 2),
                "bin": f"{b['lo']:.1f}-{b['hi']:.1f}",
                "n": b["count"],
                "mean_confidence": round(b["mean_conf"], 4),
                "accuracy": round(b["accuracy"], 4),
            })
    except Exception:
        reliability = []

    # Over-time series, one point per match day, with cumulative metrics.
    by_day: dict[str, list[dict]] = {}
    for r in resolved:
        by_day.setdefault(_period_key(r), []).append(r)
    bets_by_day: dict[str, list[dict]] = {}
    for r in bet_rows:
        bets_by_day.setdefault(_period_key(r), []).append(r)

    over_time: list[dict] = []
    cum: list[dict] = []
    cum_bets: list[dict] = []
    for day in sorted(by_day):
        day_rows = by_day[day]
        cum.extend(day_rows)
        cum_bets.extend(bets_by_day.get(day, []))
        day_score = _score(_records_from_rows(day_rows))
        cum_score = _score(_records_from_rows(cum))
        cum_bet = _bet_metrics(cum_bets)
        over_time.append({
            "period": day,
            "n": day_score.get("n", 0),
            "accuracy": day_score.get("accuracy"),
            "brier_score": day_score.get("brier_score"),
            "log_loss": day_score.get("log_loss"),
            "cumulative_accuracy": cum_score.get("accuracy"),
            "cumulative_brier": cum_score.get("brier_score"),
            "cumulative_log_loss": cum_score.get("log_loss"),
            "cumulative_roi": cum_bet.get("roi"),
            "cumulative_clv": cum_bet.get("average_clv"),
            "bets": cum_bet.get("bets", 0),
        })

    return {**base, "summary": summary, "reliability": reliability, "over_time": over_time,
            "confidence_distribution": conf_dist,
            "clv_note": None if summary.get("clv_samples") else "CLV needs closing odds — none captured."}
