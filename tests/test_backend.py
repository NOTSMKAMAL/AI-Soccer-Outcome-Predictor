import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from backend.main import app
    return TestClient(app)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_teams_returns_list(client):
    response = client.get("/api/teams")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert isinstance(data["data"], list)
    assert len(data["data"]) > 0


def test_get_teams_team_shape(client):
    response = client.get("/api/teams")
    teams = response.json()["data"]
    for team in teams:
        assert "id" in team
        assert "name" in team
        assert "country" in team


def test_predict_returns_success(client):
    response = client.post("/api/predict", json={"team_a_id": 33, "team_b_id": 2})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_predict_response_shape(client):
    response = client.post("/api/predict", json={"team_a_id": 33, "team_b_id": 2})
    pred = response.json()["data"]
    assert "winner" in pred
    assert "confidence" in pred
    assert "reasoning" in pred
    assert "comparison" in pred
    assert "teams" in pred
    assert isinstance(pred["confidence"], int)
    assert 0 <= pred["confidence"] <= 100


def test_predict_confidence_range(client):
    response = client.post("/api/predict", json={"team_a_id": 6, "team_b_id": 9})
    pred = response.json()["data"]
    assert 50 <= pred["confidence"] <= 99


def test_predict_same_team_returns_400(client):
    response = client.post("/api/predict", json={"team_a_id": 33, "team_b_id": 33})
    assert response.status_code == 400


def test_predict_comparison_keys(client):
    response = client.post("/api/predict", json={"team_a_id": 33, "team_b_id": 2})
    comparison = response.json()["data"]["comparison"]
    assert "attack" in comparison
    assert "defense" in comparison
    assert "recent_form" in comparison


def test_predictor_compute_score():
    from backend.predictor import compute_score
    stats = {"attack": 8.0, "defense": 7.0, "recent_form": 4.0}
    score = compute_score(stats)
    assert score > 0


def test_predictor_confidence_symmetric():
    from backend.predictor import compute_confidence
    # Equal scores hit the minimum confidence floor (52), not raw 50
    c1 = compute_confidence(5.0, 5.0)
    assert c1 == 52


def test_predictor_winner_selection():
    from backend.predictor import predict
    stats_strong = {"attack": 9.0, "defense": 9.0, "recent_form": 5.0}
    stats_weak = {"attack": 5.0, "defense": 5.0, "recent_form": 1.0}
    result = predict(1, "StrongTeam", 2, "WeakTeam", stats_strong, stats_weak)
    assert result["winner"] == "StrongTeam"
    assert result["confidence"] > 50


def test_soccer_api_mock_teams():
    from backend.soccer_api import SoccerApiClient
    client = SoccerApiClient()
    teams = client.get_teams()
    assert len(teams) >= 5
    names = [t["name"] for t in teams]
    assert "Argentina" in names


def test_soccer_api_mock_stats():
    from backend.soccer_api import SoccerApiClient
    client = SoccerApiClient()
    stats = client.get_team_stats(33)
    assert "attack" in stats
    assert "defense" in stats
    assert "recent_form" in stats
