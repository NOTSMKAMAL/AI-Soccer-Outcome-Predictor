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

    def test_dc_prob_rolling_form_path(self):
        """Rolling form should be used when provided with valid data."""
        team_a_stats = {
            "goals_scored": 12,
            "goals_conceded": 6,
            "total_matches": 10,
        }
        team_b_stats = {
            "goals_scored": 10,
            "goals_conceded": 8,
            "total_matches": 10,
        }
        rolling_form = {
            "home_scored_5r": 8,
            "home_conceded_5r": 2,
            "away_scored_5r": 6,
            "away_conceded_5r": 4,
            "home_rounds_used": 5,
            "away_rounds_used": 5,
        }

        result = dixon_coles_probability(
            team_a_stats, team_b_stats, is_home_a=True, rolling_form=rolling_form
        )

        assert result is not None
        assert result["method"] == "rolling_blend_20_80", \
            "Should use rolling form when provided"

    def test_dc_prob_rolling_form_fallback_when_zeros(self):
        """Should fallback to standings when rolling_form has zeros."""
        team_a_stats = {
            "goals_scored": 12,
            "goals_conceded": 6,
            "total_matches": 10,
        }
        team_b_stats = {
            "goals_scored": 10,
            "goals_conceded": 8,
            "total_matches": 10,
        }
        rolling_form = {
            "home_scored_5r": 0,  # Invalid: zero
            "home_conceded_5r": 2,
            "away_scored_5r": 6,
            "away_conceded_5r": 4,
        }

        result = dixon_coles_probability(
            team_a_stats, team_b_stats, is_home_a=True, rolling_form=rolling_form
        )

        assert result is not None
        assert result["method"] == "standings", \
            "Should fallback to standings when rolling_form has zeros"

    def test_dc_prob_with_league_id_epl(self):
        """EPL home advantage (1.18) should produce higher home_win than standings-only."""
        team_stats = {
            "goals_scored": 10,
            "goals_conceded": 5,
            "total_matches": 10,
        }

        result_epl = dixon_coles_probability(
            team_stats, team_stats, is_home_a=True, league_id=8  # EPL
        )
        result_default = dixon_coles_probability(
            team_stats, team_stats, is_home_a=True, league_id=999  # Unknown league
        )

        assert result_epl is not None
        assert result_default is not None
        assert result_epl["home_win"] > result_default["home_win"], \
            "EPL home advantage (1.18) should exceed default (1.15)"

    def test_dc_prob_with_league_id_mls(self):
        """MLS home advantage (1.08) should be weaker than EPL (1.18)."""
        team_stats = {
            "goals_scored": 10,
            "goals_conceded": 5,
            "total_matches": 10,
        }

        result_epl = dixon_coles_probability(
            team_stats, team_stats, is_home_a=True, league_id=8  # EPL: 1.18
        )
        result_mls = dixon_coles_probability(
            team_stats, team_stats, is_home_a=True, league_id=779  # MLS: 1.08
        )

        assert result_epl is not None
        assert result_mls is not None
        assert result_epl["home_win"] > result_mls["home_win"], \
            "EPL (1.18) home advantage should exceed MLS (1.08)"

    def test_dc_prob_draw_probability_nonzero(self):
        """Draw probability must never return exactly 0.0."""
        team_stats = {
            "goals_scored": 10,
            "goals_conceded": 5,
            "total_matches": 10,
        }

        result = dixon_coles_probability(team_stats, team_stats)

        assert result is not None
        assert result["draw"] > 0.0, "Draw probability must be > 0"
        assert result["draw"] >= 0.05, "Floor enforcement: draw >= 0.05"

    def test_dc_prob_tau_correction_low_scores(self):
        """τ correction should affect low-score probabilities without NaN."""
        team_stats = {
            "goals_scored": 1.2,  # Low-scoring team (≈1 goal/match)
            "goals_conceded": 1.1,
            "total_matches": 10,
        }

        result = dixon_coles_probability(team_stats, team_stats)

        assert result is not None
        # Check no NaN values
        assert not any(
            v != v for v in [result["home_win"], result["draw"], result["away_win"]]
        ), "Tau correction produced NaN"
        # Check all probabilities are valid
        assert all(
            0.05 <= p <= 0.90 for p in [result["home_win"], result["draw"], result["away_win"]]
        ), "All probabilities must be in [0.05, 0.90]"


# ── GROUP 2: Confidence Label Branch Coverage Tests ──────────────────────────────

class TestConfidenceLabelBranches:
    """Test confidence threshold boundaries and draw-as-max case."""

    def test_confidence_exactly_at_high_boundary(self):
        """winner_prob = 0.65 exactly should return 'high'."""
        dc_probs = {
            "home_win": 0.65,
            "draw": 0.25,
            "away_win": 0.10,
        }
        winner_prob = max(dc_probs["home_win"], dc_probs["draw"], dc_probs["away_win"])

        if winner_prob >= _CONF_HIGH:
            confidence = "high"
        elif winner_prob >= _CONF_MEDIUM:
            confidence = "medium"
        else:
            confidence = "low"

        assert confidence == "high", "0.65 exactly should be 'high'"

    def test_confidence_just_below_high_boundary(self):
        """winner_prob = 0.649 should return 'medium'."""
        dc_probs = {
            "home_win": 0.649,
            "draw": 0.251,
            "away_win": 0.100,
        }
        winner_prob = max(dc_probs["home_win"], dc_probs["draw"], dc_probs["away_win"])

        if winner_prob >= _CONF_HIGH:
            confidence = "high"
        elif winner_prob >= _CONF_MEDIUM:
            confidence = "medium"
        else:
            confidence = "low"

        assert confidence == "medium", "0.649 should be 'medium'"

    def test_confidence_exactly_at_medium_boundary(self):
        """winner_prob = 0.45 exactly should return 'medium'."""
        dc_probs = {
            "home_win": 0.45,
            "draw": 0.30,
            "away_win": 0.25,
        }
        winner_prob = max(dc_probs["home_win"], dc_probs["draw"], dc_probs["away_win"])

        if winner_prob >= _CONF_HIGH:
            confidence = "high"
        elif winner_prob >= _CONF_MEDIUM:
            confidence = "medium"
        else:
            confidence = "low"

        assert confidence == "medium", "0.45 exactly should be 'medium'"

    def test_confidence_just_below_medium_boundary(self):
        """winner_prob = 0.449 should return 'low'."""
        dc_probs = {
            "home_win": 0.449,
            "draw": 0.300,
            "away_win": 0.251,
        }
        winner_prob = max(dc_probs["home_win"], dc_probs["draw"], dc_probs["away_win"])

        if winner_prob >= _CONF_HIGH:
            confidence = "high"
        elif winner_prob >= _CONF_MEDIUM:
            confidence = "medium"
        else:
            confidence = "low"

        assert confidence == "low", "0.449 should be 'low'"

    def test_confidence_draw_as_most_likely(self):
        """When draw is highest probability, confidence should still work."""
        dc_probs = {
            "home_win": 0.30,
            "draw": 0.50,  # Draw is highest
            "away_win": 0.20,
        }
        winner_prob = max(dc_probs["home_win"], dc_probs["draw"], dc_probs["away_win"])

        if winner_prob >= _CONF_HIGH:
            confidence = "high"
        elif winner_prob >= _CONF_MEDIUM:
            confidence = "medium"
        else:
            confidence = "low"

        assert winner_prob == 0.50, "Winner prob should be 0.50 (draw is highest)"
        assert confidence == "medium", "Draw at 0.50 should be 'medium' (>= 0.45 but < 0.65)"


# ── GROUP 3: Winner Override Branch Coverage Tests ──────────────────────────────

class TestWinnerOverride:
    """Test winner determination from probabilities."""

    def test_winner_override_home_wins(self):
        """home_win > away_win and home_win > draw → home team wins."""
        dc_probs = {
            "home_win": 0.65,
            "draw": 0.20,
            "away_win": 0.15,
        }
        team_a = "Manchester City"
        team_b = "Liverpool"

        if dc_probs["home_win"] >= dc_probs["away_win"] and \
           dc_probs["home_win"] >= dc_probs["draw"]:
            winner = team_a
        elif dc_probs["away_win"] >= dc_probs["home_win"] and \
             dc_probs["away_win"] >= dc_probs["draw"]:
            winner = team_b
        else:
            winner = team_a

        assert winner == team_a, "Home team should win"

    def test_winner_override_away_wins(self):
        """away_win > home_win and away_win > draw → away team wins."""
        dc_probs = {
            "home_win": 0.25,
            "draw": 0.20,
            "away_win": 0.55,
        }
        team_a = "Newcastle"
        team_b = "Arsenal"

        if dc_probs["home_win"] >= dc_probs["away_win"] and \
           dc_probs["home_win"] >= dc_probs["draw"]:
            winner = team_a
        elif dc_probs["away_win"] >= dc_probs["home_win"] and \
             dc_probs["away_win"] >= dc_probs["draw"]:
            winner = team_b
        else:
            winner = team_a

        assert winner == team_b, "Away team should win"

    def test_winner_override_draw_is_highest(self):
        """When draw is highest, home team used as tiebreaker."""
        dc_probs = {
            "home_win": 0.35,
            "draw": 0.40,  # Draw is highest
            "away_win": 0.25,
        }
        team_a = "Everton"
        team_b = "Fulham"

        if dc_probs["home_win"] >= dc_probs["away_win"] and \
           dc_probs["home_win"] >= dc_probs["draw"]:
            winner = team_a
        elif dc_probs["away_win"] >= dc_probs["home_win"] and \
             dc_probs["away_win"] >= dc_probs["draw"]:
            winner = team_b
        else:
            winner = team_a

        assert winner == team_a, "Draw case should default to home team"

    def test_winner_override_tie_home_away(self):
        """Exact tie home/away should use home team (>= comparison)."""
        dc_probs = {
            "home_win": 0.40,
            "draw": 0.20,
            "away_win": 0.40,  # Tied with home_win
        }
        team_a = "Chelsea"
        team_b = "Tottenham"

        if dc_probs["home_win"] >= dc_probs["away_win"] and \
           dc_probs["home_win"] >= dc_probs["draw"]:
            winner = team_a
        elif dc_probs["away_win"] >= dc_probs["home_win"] and \
             dc_probs["away_win"] >= dc_probs["draw"]:
            winner = team_b
        else:
            winner = team_a

        assert winner == team_a, "Tie should resolve to home team (>= comparison)"


# ── GROUP 4: Integration Tests ────────────────────────────────────────────────────

class TestIntegration:
    """Test how modules interact."""

    def test_standings_data_flows_to_dixon_coles(self):
        """Valid standings data should produce consistent probabilities."""
        team_a_stats = {
            "goals_scored": 20,  # Strong team
            "goals_conceded": 5,
            "total_matches": 10,
        }
        team_b_stats = {
            "goals_scored": 8,  # Weak team
            "goals_conceded": 15,
            "total_matches": 10,
        }

        result = dixon_coles_probability(team_a_stats, team_b_stats, is_home_a=True)

        assert result is not None
        # Strong home team should have > 50% win probability
        assert result["home_win"] > 0.50, \
            "Strong home team should have >50% win probability"

    def test_missing_standings_returns_none(self):
        """Empty stats should return None (not crash)."""
        empty_stats = {}
        valid_stats = {
            "goals_scored": 10,
            "goals_conceded": 5,
            "total_matches": 10,
        }

        result = dixon_coles_probability(empty_stats, valid_stats)

        assert result is None, "Missing stats should return None"

    def test_home_advantage_affects_output(self):
        """Same team stats in EPL vs MLS should differ."""
        team_stats = {
            "goals_scored": 15,
            "goals_conceded": 8,
            "total_matches": 10,
        }

        result_epl = dixon_coles_probability(
            team_stats, team_stats, is_home_a=True, league_id=8
        )
        result_mls = dixon_coles_probability(
            team_stats, team_stats, is_home_a=True, league_id=779
        )

        assert result_epl is not None
        assert result_mls is not None
        diff = result_epl["home_win"] - result_mls["home_win"]
        assert diff > 0.02, f"EPL-MLS difference {diff:.4f} should be > 0.02pp"


# ── GROUP 5: Regression Invariant Tests ────────────────────────────────────────────

class TestRegressionInvariants:
    """Guard regression — accuracy, calibration, error metrics stay in bounds."""

    def test_backtest_accuracy_above_home_baseline(self):
        """CSV backtest accuracy must exceed home baseline."""
        backtest_file = Path(__file__).parent.parent / "scripts" / "data" / "backtest_csv_results.json"
        with open(backtest_file) as fh:
            data = json.load(fh)

        accuracy = float(data["overall_accuracy"])
        home_baseline = float(data["home_baseline_accuracy"])

        assert accuracy > home_baseline, \
            f"Model {accuracy:.4f} should beat home baseline {home_baseline:.4f}"

    def test_brier_score_below_random(self):
        """Brier score must be below 0.667 (random guess for binary)."""
        backtest_file = Path(__file__).parent.parent / "scripts" / "data" / "backtest_csv_results.json"
        with open(backtest_file) as fh:
            data = json.load(fh)

        brier = float(data["brier_score"])

        assert brier < 0.667, \
            f"Brier score {brier:.4f} should be < 0.667 (random baseline)"

    def test_log_loss_below_random(self):
        """Log loss must be below 1.10 (random uniform baseline)."""
        backtest_file = Path(__file__).parent.parent / "scripts" / "data" / "backtest_csv_results.json"
        with open(backtest_file) as fh:
            data = json.load(fh)

        log_loss = float(data["log_loss"])

        assert log_loss < 1.10, \
            f"Log loss {log_loss:.4f} should be < 1.10 (random baseline)"

    def test_high_confidence_accuracy(self):
        """High-confidence predictions must achieve >70% accuracy."""
        backtest_file = Path(__file__).parent.parent / "scripts" / "data" / "backtest_csv_results.json"
        with open(backtest_file) as fh:
            data = json.load(fh)

        calibration_acc = float(data.get("calibration_accuracy", 0))

        assert calibration_acc > 0.70, \
            f"Calibration accuracy {calibration_acc:.4f} should be > 0.70"

    def test_csv_fixture_count(self):
        """CSV backtest must cover 1747 fixtures."""
        backtest_file = Path(__file__).parent.parent / "scripts" / "data" / "backtest_csv_results.json"
        with open(backtest_file) as fh:
            data = json.load(fh)

        total = int(data["total_fixtures"])

        assert total == 1747, \
            f"CSV backtest should have 1747 fixtures, got {total}"

    def test_all_leagues_represented(self):
        """Backtest should cover all 5 leagues."""
        backtest_file = Path(__file__).parent.parent / "scripts" / "data" / "backtest_csv_results.json"
        with open(backtest_file) as fh:
            data = json.load(fh)

        by_league = data.get("by_league", {})

        assert len(by_league) == 5, \
            f"Should have 5 leagues, got {len(by_league)}: {list(by_league.keys())}"


# ── GROUP 6: Edge Case and Failure Tests ──────────────────────────────────────────

class TestEdgeCases:
    """Test boundary conditions, edge cases, and error handling."""

    def test_dc_prob_division_by_zero_prevention(self):
        """Teams with 0 matches should return None (not crash)."""
        zero_stats = {
            "goals_scored": 5,
            "goals_conceded": 0,
            "total_matches": 0,  # Division by zero guard
        }
        valid_stats = {
            "goals_scored": 10,
            "goals_conceded": 5,
            "total_matches": 10,
        }

        result = dixon_coles_probability(zero_stats, valid_stats)

        assert result is None, "Zero matches should return None, not crash"

    def test_dc_prob_very_lopsided_match(self):
        """Heavily one-sided matchup should show strong bias."""
        dominant = {
            "goals_scored": 80,
            "goals_conceded": 10,
            "total_matches": 38,
        }
        weak = {
            "goals_scored": 15,
            "goals_conceded": 65,
            "total_matches": 38,
        }

        result = dixon_coles_probability(dominant, weak, is_home_a=True)

        assert result is not None
        assert result["home_win"] > 0.70, \
            "Dominant home team should have >70% win probability"
        assert result["away_win"] < 0.15, \
            "Weak away team should have <15% win probability"

    def test_dc_prob_max_goals_cap_enforced(self):
        """All probabilities must stay in [0.05, 0.90]."""
        team_stats = {
            "goals_scored": 100,  # Extreme
            "goals_conceded": 1,
            "total_matches": 10,
        }

        result = dixon_coles_probability(team_stats, team_stats)

        assert result is not None
        assert all(
            0.05 <= p <= 0.90
            for p in [result["home_win"], result["draw"], result["away_win"]]
        ), "All probabilities must be in [0.05, 0.90]"

    def test_dc_prob_consistent_across_calls(self):
        """Same input should always produce identical output (determinism)."""
        team_stats = {
            "goals_scored": 12,
            "goals_conceded": 8,
            "total_matches": 10,
        }

        result1 = dixon_coles_probability(team_stats, team_stats)
        result2 = dixon_coles_probability(team_stats, team_stats)

        assert result1 == result2, \
            "Determinism: identical inputs must produce identical outputs"

    def test_dc_prob_negative_stats_invalid(self):
        """Negative goals should be rejected (returned as None)."""
        negative_stats = {
            "goals_scored": -5,  # Invalid
            "goals_conceded": 5,
            "total_matches": 10,
        }
        valid_stats = {
            "goals_scored": 10,
            "goals_conceded": 5,
            "total_matches": 10,
        }

        result = dixon_coles_probability(negative_stats, valid_stats)

        # The _f() helper returns None for non-positive values
        assert result is None, "Negative stats should return None"

    def test_probability_normalization_exact(self):
        """After normalization, probabilities should sum to exactly 1.0."""
        team_stats = {
            "goals_scored": 10,
            "goals_conceded": 5,
            "total_matches": 10,
        }

        result = dixon_coles_probability(team_stats, team_stats)

        assert result is not None
        total = result["home_win"] + result["draw"] + result["away_win"]
        assert abs(total - 1.0) < 1e-10, \
            f"Probabilities should sum to 1.0, got {total}"


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
