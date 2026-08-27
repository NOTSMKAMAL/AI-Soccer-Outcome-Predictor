"""Tests for the 0-100 confidence score and richer betting signal (Priority 5/6)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scoring


def test_confidence_score_orders_examples():
    # The spec's example: a lopsided favorite should score higher than a near-even
    # three-way with a big draw chance.
    france = scoring.confidence_score({"home_win": 0.64, "draw": 0.22, "away_win": 0.14})
    norway = scoring.confidence_score({"home_win": 0.36, "draw": 0.28, "away_win": 0.36})
    assert france > norway
    assert scoring.confidence_band(france) == "high"
    assert scoring.confidence_band(norway) == "low"


def test_confidence_score_bounds_and_band():
    assert 0 <= scoring.confidence_score({"home_win": 0.34, "draw": 0.33, "away_win": 0.33}) <= 100
    assert scoring.confidence_band(80) == "high"
    assert scoring.confidence_band(50) == "medium"
    assert scoring.confidence_band(20) == "low"
    assert scoring.confidence_band(95, unknown=True) == "low"   # unknown forces low


def test_draw_probability_penalizes_confidence():
    low_draw = scoring.confidence_score({"home_win": 0.55, "draw": 0.20, "away_win": 0.25})
    high_draw = scoring.confidence_score({"home_win": 0.55, "draw": 0.40, "away_win": 0.05})
    assert high_draw < low_draw


def test_data_quality_and_calibration_raise_score():
    base = scoring.confidence_score({"home_win": 0.5, "draw": 0.25, "away_win": 0.25},
                                    data_quality="missing", calibration_reliability=0.0)
    better = scoring.confidence_score({"home_win": 0.5, "draw": 0.25, "away_win": 0.25},
                                      data_quality="ok", calibration_reliability=1.0)
    assert better > base


def test_betting_signal_tiers():
    assert scoring.betting_signal(10.0, "low", 80) == "Strong Value"
    assert scoring.betting_signal(5.0, "medium", 60) == "Value"
    assert scoring.betting_signal(1.0, "low", 60) == "Neutral"
    assert scoring.betting_signal(-6.0, "low", 80) == "Avoid"
    assert scoring.betting_signal(5.0, "high", 80) == "High Risk Avoid"   # thin edge + high risk
    assert scoring.betting_signal(None, "low", 80) is None


def test_high_edge_high_risk_is_not_strong_value():
    # A big edge on a high-risk pick must not be flagged Strong Value.
    assert scoring.betting_signal(12.0, "high", 90) != "Strong Value"
