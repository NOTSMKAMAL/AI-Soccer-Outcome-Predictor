import pytest
import requests
from unittest.mock import patch, MagicMock
from storage.sportmonks_client import get_team_stats, get_head_to_head, check_team_data


def make_mock_response(json_data, status_code=200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.raise_for_status = MagicMock()
    return mock


@patch("storage.sportmonks_client.requests.get")
def test_get_team_stats_success(mock_get):
    mock_get.return_value = make_mock_response({"data": {"id": 85, "name": "Man City"}})
    result = get_team_stats(85)
    assert result["status"] == "success"
    assert result["data"]["name"] == "Man City"


@patch("storage.sportmonks_client.requests.get")
def test_get_team_stats_http_error(mock_get):
    mock_get.return_value = make_mock_response({}, status_code=404)
    mock_get.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
    result = get_team_stats(99999)
    assert result["status"] == "error"
    assert "HTTP error" in result["message"]


@patch("storage.sportmonks_client.requests.get")
def test_check_team_data_both_ready(mock_get):
    mock_get.return_value = make_mock_response({"data": {"id": 85, "name": "Man City"}})
    result = check_team_data(85, 86)
    assert result["status"] == "success"
    assert result["data"]["team_a_ready"] is True
    assert result["data"]["team_b_ready"] is True