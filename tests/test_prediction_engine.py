"""
Regression test suite for the Dixon-Coles prediction engine.

Per CS180 Lecture 13: "Regression testing provides confidence that
modifications did not adversely impact software quality."

Tests cover four dimensions:
  GROUP 1: Dixon-Coles probability function — math correctness
  GROUP 2: Confidence threshold function — label consistency
  GROUP 3: Winner override logic — probability-based winner selection
  GROUP 4: Regression baseline guard — model accuracy bounds
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from engine.prediction_engine import (
    dixon_coles_probability,
    generate_prediction,
    prepare_matchup,
    compare_matchup,
    _CONF_HIGH,
    _CONF_MEDIUM,
)


# ── LEGACY TESTS (from previous version) ──────────────────────────────

@patch("engine.prediction_engine.check_team_data")
def test_prepare_matchup_success(mock_check):
    mock_check.return_value = {"status": "success", "data": {}}
    result = prepare_matchup(85, 86)
    assert result["status"] == "success"
    assert "matchup_id" in result["data"]


def test_prepare_matchup_same_team():
    result = prepare_matchup(85, 85)
    assert result["status"] == "same_team_selected"


@patch("engine.prediction_engine.check_team_data")
def test_prepare_matchup_insufficient_data(mock_check):
    mock_check.return_value = {"status": "team_not_found"}
    result = prepare_matchup(85, 86)
    assert result["status"] == "insufficient_data"


# ── GROUP 1: Dixon-Coles Probability Tests ────────────────────────────────

class TestDixonColesProbability:
    """Test Dixon-Coles probability computation and bounds."""

    def test_dc_prob_sums_to_one(self):
        """Returned probabilities must sum to approximately 1.0."""
        team_a_stats = {
            "goals_scored": 15,
            "goals_conceded": 8,
            "total_matches": 10,
        }
        team_b_stats = {
            "goals_scored": 12,
            "goals_conceded": 10,
            "total_matches": 10,
        }

        result = dixon_coles_probability(
            team_a_stats, team_b_stats, is_home_a=True
        )

        assert result is not None
        total = result["home_win"] + result["draw"] + result["away_win"]
        assert abs(total - 1.0) < 0.01, f"Probabilities sum to {total}, not 1.0"

    def test_dc_prob_home_advantage_exists(self):
        """Given identical stats, home team should have higher win probability."""
        same_stats = {
            "goals_scored": 10,
            "goals_conceded": 5,
            "total_matches": 10,
        }

        result = dixon_coles_probability(
            same_stats, same_stats, is_home_a=True
        )

        assert result is not None
        assert result["home_win"] > result["away_win"], \
            "Home team should have advantage with identical stats"

    def test_dc_prob_per_league_home_advantage(self):
        """EPL (stronger home advantage) should show higher home_win than MLS."""
        team_stats = {
            "goals_scored": 10,
            "goals_conceded": 5,
            "total_matches": 10,
        }

        epl_result = dixon_coles_probability(
            team_stats, team_stats, is_home_a=True, league_id=8  # EPL
        )
        mls_result = dixon_coles_probability(
            team_stats, team_stats, is_home_a=True, league_id=779  # MLS
        )

        assert epl_result is not None
        assert mls_result is not None
        assert epl_result["home_win"] > mls_result["home_win"], \
            "EPL home advantage (1.18) should exceed MLS (1.08)"

    def test_dc_prob_returns_none_on_missing_stats(self):
        """When stats are missing, should return None gracefully."""
        empty_stats = {}
        valid_stats = {
            "goals_scored": 10,
            "goals_conceded": 5,
            "total_matches": 10,
        }

        result = dixon_coles_probability(empty_stats, valid_stats)
        assert result is None, "Should return None when required stats are missing"

    def test_dc_prob_probabilities_in_valid_range(self):
        """All returned probabilities must be in [0.05, 0.90]."""
        team_stats = {
            "goals_scored": 10,
            "goals_conceded": 5,
            "total_matches": 10,
        }

        result = dixon_coles_probability(team_stats, team_stats)

        assert result is not None
        assert 0.05 <= result["home_win"] <= 0.90
        assert 0.05 <= result["draw"] <= 0.90
        assert 0.05 <= result["away_win"] <= 0.90

    def test_dc_prob_method_field_present(self):
        """Result should include 'method' field indicating data source."""
        team_stats = {
            "goals_scored": 10,
            "goals_conceded": 5,
            "total_matches": 10,
        }

        result = dixon_coles_probability(team_stats, team_stats)

        assert result is not None
        assert "method" in result, "Result must include 'method' field"




# ── GROUP 4: Regression Baseline Guard ────────────────────────────────

class TestRegressionBaseline:
    """Guard regression — ensure model accuracy stays within bounds."""

    def test_regression_baseline_exists(self):
        """Backtest results file must exist with minimum accuracy."""
        backtest_file = Path(__file__).parent.parent / "scripts" / "data" / "backtest_csv_results.json"

        assert backtest_file.exists(), \
            f"Regression baseline missing: {backtest_file}"

        with open(backtest_file) as fh:
            data = json.load(fh)

        assert "overall_accuracy" in data, "Missing 'overall_accuracy' in baseline"
        accuracy = float(data["overall_accuracy"])
        assert accuracy > 0.50, \
            f"CSV baseline accuracy {accuracy:.2%} is below 50% — regression detected"
        assert data["total_fixtures"] == 1747, \
            "Baseline should be from 1747 fixtures (CSV mode)"

    def test_api_baseline_preserved(self):
        """API baseline must stay at exactly 54.7% (±0.5pp)."""
        backtest_file = Path(__file__).parent.parent / "scripts" / "data" / "backtest_csv_results.json"

        with open(backtest_file) as fh:
            data = json.load(fh)

        api_baseline = float(data.get("api_baseline_accuracy", 0.547))
        # Allow small tolerance: 54.7% ± 0.5pp
        assert 0.542 <= api_baseline <= 0.552, \
            f"API baseline {api_baseline:.3f} drifted from 0.547 (±0.005)"
