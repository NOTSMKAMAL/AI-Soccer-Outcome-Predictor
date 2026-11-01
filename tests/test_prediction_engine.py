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
from google.genai.errors import ClientError, ServerError

from engine.prediction_engine import (
    _build_enriched_section,
    cached_prediction,
    dixon_coles_probability,
    generate_prediction,
    prepare_matchup,
    compare_matchup,
    DRAW_OUTCOME,
    _CONF_HIGH,
    _CONF_MEDIUM,
    _predicted_outcome,
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

    def test_a_failed_standings_fetch_is_not_remembered(self):
        """A rate-limited moment must not leave a league without numbers until a restart."""
        standings = {
            57: {"goals_scored_per_game": 2.1, "goals_conceded_per_game": 0.8, "matches_played": 10, "clean_sheets": 0},
            61: {"goals_scored_per_game": 1.2, "goals_conceded_per_game": 1.4, "matches_played": 10, "clean_sheets": 0},
        }
        with patch("engine.prediction_engine.get_season_team_stats", return_value={}) as stats:
            assert dixon_coles_probability({}, {}, season_id="PL", team_a_id=57, team_b_id=61) is None
            stats.return_value = standings
            assert dixon_coles_probability({}, {}, season_id="PL", team_a_id=57, team_b_id=61) is not None


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

        winner = _predicted_outcome(dc_probs, team_a, team_b)

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

        winner = _predicted_outcome(dc_probs, team_a, team_b)

        assert winner == team_b, "Away team should win"

    def test_winner_override_draw_is_highest(self):
        """When draw is highest, the verdict is a draw, not a team."""
        dc_probs = {
            "home_win": 0.35,
            "draw": 0.40,  # Draw is highest
            "away_win": 0.25,
        }
        team_a = "Everton"
        team_b = "Fulham"

        winner = _predicted_outcome(dc_probs, team_a, team_b)

        assert winner == DRAW_OUTCOME, "A draw-led match must not be called for a team"

    def test_winner_override_tie_with_draw(self):
        """An exact tie with the draw goes to the team (>= comparison)."""
        team_a = "Everton"
        team_b = "Fulham"

        home_tied = {"home_win": 0.40, "draw": 0.40, "away_win": 0.20}
        away_tied = {"home_win": 0.20, "draw": 0.40, "away_win": 0.40}

        assert _predicted_outcome(home_tied, team_a, team_b) == team_a
        assert _predicted_outcome(away_tied, team_a, team_b) == team_b

    def test_winner_override_tie_home_away(self):
        """Exact tie home/away should use home team (>= comparison)."""
        dc_probs = {
            "home_win": 0.40,
            "draw": 0.20,
            "away_win": 0.40,  # Tied with home_win
        }
        team_a = "Chelsea"
        team_b = "Tottenham"

        winner = _predicted_outcome(dc_probs, team_a, team_b)

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

    def test_high_confidence_predictions_beat_overall(self):
        """
        Confidence must be informative: high-confidence (>=65%) predictions must
        be MORE accurate than the overall rate. The honest point-in-time baseline
        is ~59.3% high-conf vs ~48.4% overall. The old >0.70 bar defended the
        lookahead-contaminated 73.7% and is intentionally retired.
        """
        backtest_file = Path(__file__).parent.parent / "scripts" / "data" / "backtest_csv_results.json"
        with open(backtest_file) as fh:
            data = json.load(fh)

        calibration_acc = float(data.get("calibration_accuracy", 0))
        overall_acc = float(data["overall_accuracy"])

        assert calibration_acc > overall_acc, \
            f"High-confidence accuracy {calibration_acc:.4f} should exceed overall {overall_acc:.4f}"

    def test_csv_baseline_is_point_in_time(self):
        """Guard: the canonical baseline must be the honest, no-lookahead run."""
        backtest_file = Path(__file__).parent.parent / "scripts" / "data" / "backtest_csv_results.json"
        with open(backtest_file) as fh:
            data = json.load(fh)

        assert data.get("point_in_time") is True, \
            "backtest_csv_results.json must be the point-in-time (no-lookahead) baseline, " \
            "not the leaky full-season-aggregate run."

    def test_csv_fixture_count(self):
        """
        Point-in-time evaluated set: 1747 loaded minus per-team warm-up skips.
        1526 is the honest no-lookahead count.
        """
        backtest_file = Path(__file__).parent.parent / "scripts" / "data" / "backtest_csv_results.json"
        with open(backtest_file) as fh:
            data = json.load(fh)

        total = int(data["total_fixtures"])

        assert total == 1526, \
            f"Point-in-time CSV backtest should evaluate 1526 fixtures, got {total}"

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
        home_baseline = float(data["home_baseline_accuracy"])
        # Honest point-in-time accuracy (~48.4%) is BELOW 50% — the old >0.50 bar
        # defended the lookahead-inflated number. The real guardrail is that the
        # model still beats the always-pick-home baseline.
        assert accuracy > home_baseline, \
            f"CSV baseline accuracy {accuracy:.2%} must beat home baseline {home_baseline:.2%}"
        assert data["total_fixtures"] == 1526, \
            "Point-in-time baseline should evaluate 1526 fixtures (CSV mode)"

    def test_api_baseline_preserved(self):
        """API baseline must stay at exactly 54.7% (±0.5pp)."""
        backtest_file = Path(__file__).parent.parent / "scripts" / "data" / "backtest_csv_results.json"

        with open(backtest_file) as fh:
            data = json.load(fh)

        api_baseline = float(data.get("api_baseline_accuracy", 0.547))
        # Allow small tolerance: 54.7% ± 0.5pp
        assert 0.542 <= api_baseline <= 0.552, \
            f"API baseline {api_baseline:.3f} drifted from 0.547 (±0.005)"

    def test_all_active_leagues_in_home_advantage(self):
        """Every active competition must have an explicit home advantage coefficient.

        Per CS180 NITR structural oracle: prevents future leagues being added to
        the supported list without a calibrated coefficient, which causes silent
        fallback to the default 1.15 value and less accurate predictions.
        """
        from storage.league_data_client import COMPETITION_IDS
        from engine.prediction_engine import _HOME_ADVANTAGE

        for league_id in COMPETITION_IDS.values():
            assert league_id in _HOME_ADVANTAGE, (
                f"Competition {league_id} is supported but missing from "
                f"_HOME_ADVANTAGE — add a calibrated coefficient or remove the league."
            )


# ── GROUP 5: Degraded enrichment — caching and prompt ──────────────────────────

_NO_H2H = {"status": "success", "data": {
    "team_a_wins": 0, "team_b_wins": 0, "draws": 0, "total_h2h": 0, "recent_results": [],
}}
_DC_PROBS = {"home_win": 0.2, "draw": 0.2, "away_win": 0.6, "method": "test"}
_GEMINI_TEXT = "Winner: Away FC\nConfidence: high\nReasoning: Away FC are 1st with 17 points."


@pytest.fixture
def fake_gemini():
    """Mock Gemini and the H2H/Dixon-Coles inputs; yield the generate_content mock."""
    import engine.prediction_engine as pe
    pe._prediction_cache.clear()
    with patch.object(pe, "compare_matchup", return_value=_NO_H2H), \
         patch.object(pe, "dixon_coles_probability", return_value=_DC_PROBS), \
         patch.object(pe, "client") as client:
        client.models.generate_content.return_value.text = _GEMINI_TEXT
        yield client.models.generate_content
    pe._prediction_cache.clear()


def _predict(enriched):
    return generate_prediction(1, 2, "Home FC", "Away FC", enriched)


def _prompt_sent(generate_content) -> str:
    return generate_content.call_args.kwargs["contents"]


_DRAW_LED_PROBS = {"home_win": 0.32, "draw": 0.40, "away_win": 0.28, "method": "test"}


class TestDrawIsMostLikely:
    """When a draw leads, the verdict says so: the model decides, never a home default or Gemini."""

    def _predict_draw_led(self):
        import engine.prediction_engine as pe
        with patch.object(pe, "dixon_coles_probability", return_value=_DRAW_LED_PROBS):
            return _predict({"missing_sections": []})

    def test_winner_is_draw(self, fake_gemini):
        assert self._predict_draw_led()["data"]["winner"] == "Draw"

    def test_gemini_cannot_name_a_team_instead(self, fake_gemini):
        fake_gemini.return_value.text = "Winner: Home FC\nConfidence: high\nReasoning: Home FC win."
        assert self._predict_draw_led()["data"]["winner"] == "Draw"

    def test_prompt_asks_for_a_draw_explanation(self, fake_gemini):
        self._predict_draw_led()
        prompt = _prompt_sent(fake_gemini)
        assert "PREDICTED RESULT: Draw" in prompt
        assert "Your Winner field MUST be: Draw" in prompt

    def test_prompt_never_says_a_team_will_win(self, fake_gemini):
        self._predict_draw_led()
        prompt = _prompt_sent(fake_gemini)
        assert "PREDICTED WINNER" not in prompt
        assert "Home FC is predicted to win" not in prompt

    def test_confidence_comes_from_the_draw_probability(self, fake_gemini):
        assert self._predict_draw_led()["data"]["confidence"] == "low"

    def test_probabilities_are_unchanged(self, fake_gemini):
        data = self._predict_draw_led()["data"]
        assert (data["home_win_probability"], data["draw_probability"], data["away_win_probability"]) \
            == (0.32, 0.40, 0.28)

    def test_stored_verdict_is_scored_as_a_draw(self, fake_gemini):
        from storage.prediction_db import _winner_side
        winner = self._predict_draw_led()["data"]["winner"]
        stored = {"predicted_winner": winner, "home_team": "Home FC", "away_team": "Away FC"}
        assert _winner_side(stored) == "draw"

    def test_a_team_win_still_names_the_team(self, fake_gemini):
        assert _predict({"missing_sections": []})["data"]["winner"] == "Away FC"
        assert "PREDICTED WINNER: Away FC" in _prompt_sent(fake_gemini)


class TestNotEnoughData:
    """No Dixon-Coles numbers means no prediction: Gemini never stands in for the model."""

    @pytest.fixture
    def no_model(self, fake_gemini):
        import engine.prediction_engine as pe
        with patch.object(pe, "dixon_coles_probability", return_value=None):
            yield fake_gemini

    def test_missing_standings_give_no_prediction(self, no_model):
        assert _predict({"missing_sections": ["standings"]}) == {"status": "insufficient_data"}

    def test_failed_enrichment_gives_no_prediction(self, fake_gemini):
        assert _predict(None) == {"status": "insufficient_data"}

    def test_empty_enrichment_gives_no_prediction(self, fake_gemini):
        assert _predict({}) == {"status": "insufficient_data"}

    def test_gemini_is_never_called(self, no_model):
        _predict({"missing_sections": ["standings"]})
        no_model.assert_not_called()

    def test_nothing_is_cached(self, no_model):
        import engine.prediction_engine as pe
        _predict({"missing_sections": ["standings"]})
        assert pe._prediction_cache == {}

    def test_a_later_attempt_with_standings_succeeds(self, fake_gemini):
        import engine.prediction_engine as pe
        with patch.object(pe, "dixon_coles_probability", return_value=None):
            assert _predict({"missing_sections": ["standings"]})["status"] == "insufficient_data"
        assert _predict({"missing_sections": []})["status"] == "success"

    def test_a_prediction_is_always_marked_dixon_coles(self, fake_gemini):
        data = _predict({"missing_sections": []})["data"]
        assert data["probability_method"] == "dixon-coles"
        assert data["home_win_probability"] == _DC_PROBS["home_win"]


class TestDegradedEnrichment:
    """A rate-limited fetch must not pin a stats-free prediction to a matchup."""

    def test_complete_enrichment_is_cached(self, fake_gemini):
        complete = {"missing_sections": []}
        _predict(complete)
        _predict(complete)
        assert fake_gemini.call_count == 1

    def test_partial_enrichment_is_not_cached(self, fake_gemini):
        partial = {"missing_sections": ["standings"]}
        _predict(partial)
        _predict(partial)
        assert fake_gemini.call_count == 2

    def test_complete_retry_after_partial_is_cached(self, fake_gemini):
        _predict({"missing_sections": ["standings"]})
        _predict({"missing_sections": []})
        _predict({"missing_sections": []})
        assert fake_gemini.call_count == 2

    def test_prompt_names_missing_sections(self, fake_gemini):
        _predict({"missing_sections": ["standings", "team_b_recent_form"]})
        prompt = _prompt_sent(fake_gemini)
        assert "DATA LIMITATIONS" in prompt
        assert "the league standings and season statistics" in prompt
        assert "the away team's recent form" in prompt
        assert "say plainly that the data is limited" in prompt

    def test_prompt_has_no_limitations_note_when_complete(self, fake_gemini):
        _predict({"missing_sections": []})
        assert "DATA LIMITATIONS" not in _prompt_sent(fake_gemini)

    def test_gemini_called_once_without_search_tools(self, fake_gemini):
        _predict({"missing_sections": []})
        assert fake_gemini.call_count == 1
        assert "tools" not in fake_gemini.call_args.kwargs

    def test_prompt_has_no_search_instruction(self, fake_gemini):
        _predict({"missing_sections": []})
        assert "Google Search" not in _prompt_sent(fake_gemini)

    def test_gemini_failure_reports_reasoning_failed_and_is_not_cached(self, fake_gemini):
        fake_gemini.side_effect = RuntimeError("503 model overloaded")
        result = _predict({"missing_sections": []})
        assert result == {"status": "reasoning_failed", "message": "503 model overloaded"}

        fake_gemini.side_effect = None
        assert _predict({"missing_sections": []})["status"] == "success"
        assert fake_gemini.call_count == 2

    def test_cached_prediction_returns_a_complete_prediction(self, fake_gemini):
        result = _predict({"missing_sections": []})
        assert cached_prediction(1, 2, "Home FC", "Away FC") == result

    def test_cached_prediction_is_none_before_any_prediction(self, fake_gemini):
        assert cached_prediction(1, 2, "Home FC", "Away FC") is None

    def test_cached_prediction_is_none_after_a_partial_prediction(self, fake_gemini):
        _predict({"missing_sections": ["standings"]})
        assert cached_prediction(1, 2, "Home FC", "Away FC") is None

    def test_prompt_does_not_claim_head_to_head_history_is_absent(self, fake_gemini):
        # The free tier can't supply H2H, so "none exists" would be a false fact.
        _predict({"missing_sections": []})
        prompt = _prompt_sent(fake_gemini)
        assert "No head-to-head history exists" not in prompt
        assert "Head-to-head history is not available" in prompt

    def test_prompt_invents_no_injury_news(self):
        section = _build_enriched_section("Home FC", "Away FC", 1, 2, {"injuries": None})
        assert "Full squad" not in section
        assert "INJURY" not in section

    def test_prompt_names_injuries_when_a_provider_supplies_them(self):
        injuries = {"team_a": [{"player_name": "A. Player"}], "team_b": []}
        section = _build_enriched_section("Home FC", "Away FC", 1, 2, {"injuries": injuries})
        assert "A. Player" in section

    def test_prompt_has_no_clean_sheet_figure(self):
        section = _build_enriched_section("Home FC", "Away FC", 1, 2, {
            "team_a_stats": {"goals_scored": 5, "clean_sheets": None},
        })
        assert "clean sheets" not in section

    def test_gemini_overload_is_retried_once(self, fake_gemini):
        ok = fake_gemini.return_value
        fake_gemini.side_effect = [ServerError(503, {"error": {"message": "high demand"}}), ok]
        with patch("engine.prediction_engine.time.sleep") as sleep:
            result = _predict({"missing_sections": []})
        assert result["status"] == "success"
        assert fake_gemini.call_count == 2
        sleep.assert_called_once()

    def test_gemini_overload_twice_reports_reasoning_failed(self, fake_gemini):
        fake_gemini.side_effect = ServerError(503, {"error": {"message": "high demand"}})
        with patch("engine.prediction_engine.time.sleep"):
            result = _predict({"missing_sections": []})
        assert result["status"] == "reasoning_failed"
        assert fake_gemini.call_count == 2

    def test_non_server_gemini_error_is_not_retried(self, fake_gemini):
        fake_gemini.side_effect = ClientError(400, {"error": {"message": "bad request"}})
        assert _predict({"missing_sections": []})["status"] == "reasoning_failed"
        assert fake_gemini.call_count == 1

    def test_prompt_never_invites_general_knowledge(self, fake_gemini):
        import engine.prediction_engine as pe
        for enriched in ({"missing_sections": []}, {"missing_sections": ["standings"]}):
            pe._prediction_cache.clear()  # the complete case caches; each case needs a fresh call
            fake_gemini.reset_mock()
            _predict(enriched)
            assert "Use your general knowledge" not in _prompt_sent(fake_gemini)
