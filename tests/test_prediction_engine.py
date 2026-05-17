from unittest.mock import patch
from engine.prediction_engine import prepare_matchup, compare_matchup


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
