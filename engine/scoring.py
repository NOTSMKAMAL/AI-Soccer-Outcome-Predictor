"""Shared prediction scoring: confidence tiers, risk level, value signal.

Single source of truth for how a model probability becomes a confidence label,
a betting risk level, and a market value signal — so the prediction engine
(engine/prediction_engine.py), the offline backtest and the runtime tracking all
score a prediction the same way.

Pure functions, no I/O. Thresholds were calibrated on the backtest.
"""
from __future__ import annotations

# Confidence thresholds on the winning-outcome probability.
# Point-in-time backtest: high-confidence (>=65%) predictions hit ~59.3% accuracy.
CONF_HIGH = 0.65    # winner prob >= 65% -> high
CONF_MEDIUM = 0.45  # winner prob >= 45% -> medium ; below -> low

# A draw this likely makes a single-team pick materially less reliable.
HIGH_DRAW_PROB = 0.35

# Market edge bands (model probability minus market-implied probability).
VALUE_EDGE = 0.05


def confidence_from_prob(winner_prob: float, unknown: bool = False) -> str:
    """Map the winning outcome's probability to 'low' | 'medium' | 'high'.

    `unknown=True` (e.g. an unrated team) always yields 'low'.
    """
    if unknown:
        return "low"
    if winner_prob >= CONF_HIGH:
        return "high"
    if winner_prob >= CONF_MEDIUM:
        return "medium"
    return "low"


def compute_risk_level(confidence: str, draw_prob: float | None = None) -> str:
    """Map confidence to a betting risk level: high conf -> low risk, etc.

    A very high draw probability (>= HIGH_DRAW_PROB) bumps risk up one level,
    since a likely draw undermines a single-winner pick. Returns 'low'|'medium'|'high'.
    """
    base = {"high": "low", "medium": "medium", "low": "high"}.get(confidence, "high")
    if draw_prob is not None and draw_prob >= HIGH_DRAW_PROB:
        base = {"low": "medium", "medium": "high", "high": "high"}[base]
    return base


def compute_value_signal(model_prob: float, market_prob: float | None) -> str | None:
    """Compare model probability vs market-implied probability.

    Returns 'Good Value' | 'Fair Market' | 'Avoid', or None when no market exists.
    """
    if market_prob is None:
        return None
    diff = model_prob - market_prob
    if diff > VALUE_EDGE:
        return "Good Value"
    if diff < -VALUE_EDGE:
        return "Avoid"
    return "Fair Market"


# ── Richer confidence score (Priority 5) ──────────────────────────────────────

def confidence_score(
    probs: dict,
    draw_prob: float | None = None,
    calibration_reliability: float | None = None,
    market_agreement: float | None = None,
    data_quality: str = "ok",
) -> int:
    """A 0-100 confidence score from multiple quality signals.

    Components (best case sums to ~100, draw penalty subtracts):
      - probability gap (favorite minus runner-up)         up to 45
      - absolute favorite strength                          up to 20
      - historical calibration reliability (0..1)           up to 10
      - market agreement (0..1, 1 = model agrees w/ market) up to 10
      - data quality (ok / partial / missing)               up to 15
      - high draw probability penalty                       down to -15

    So a lopsided, well-calibrated, market-agreed pick on good data scores high,
    while a near-even three-way with a big draw chance scores low. Inputs default
    to neutral so the score is always computable.
    """
    vals = sorted((probs.get("home_win", 0.0), probs.get("draw", 0.0),
                   probs.get("away_win", 0.0)), reverse=True)
    top, second = vals[0], vals[1]
    gap = top - second

    score = min(45.0, gap * 100.0)
    score += min(20.0, max(0.0, (top - 0.34)) * 60.0)

    dp = draw_prob if draw_prob is not None else probs.get("draw", 0.0)
    if dp > 0.30:
        score -= min(15.0, (dp - 0.30) * 100.0)

    cr = 0.5 if calibration_reliability is None else max(0.0, min(1.0, calibration_reliability))
    score += 10.0 * cr
    ma = 0.5 if market_agreement is None else max(0.0, min(1.0, market_agreement))
    score += 10.0 * ma
    score += {"ok": 15.0, "partial": 7.0, "missing": 0.0}.get(data_quality, 7.0)

    return int(max(0, min(100, round(score))))


def confidence_band(score: int, unknown: bool = False) -> str:
    """Map a 0-100 confidence score to 'low' | 'medium' | 'high'."""
    if unknown:
        return "low"
    if score >= 66:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


# ── Richer betting signal (Priority 6) ────────────────────────────────────────

def betting_signal(edge_pts: float | None, risk_level: str | None,
                   conf_score: int | None) -> str | None:
    """Expected-quality betting signal, not raw edge alone.

    `edge_pts` is the model-minus-market edge in PERCENTAGE POINTS. The edge is
    gated by risk level and confidence so a thin edge on a high-risk, low-confidence
    pick is not flagged as value.

    Returns 'Strong Value' | 'Value' | 'Neutral' | 'Avoid' | 'High Risk Avoid' | None.
    """
    if edge_pts is None:
        return None
    cs = conf_score if conf_score is not None else 50
    if edge_pts <= -4.0:
        return "Avoid"
    if risk_level == "high" and edge_pts < 8.0:
        return "High Risk Avoid"
    if edge_pts >= 8.0 and cs >= 66 and risk_level != "high":
        return "Strong Value"
    if edge_pts >= 4.0 and cs >= 45:
        return "Value"
    return "Neutral"
