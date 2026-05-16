from flask import Flask, request, jsonify, render_template_string
from engine.prediction_engine import prepare_matchup, generate_prediction

app = Flask(__name__)

# Simple HTML template — no separate file needed
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>AI Sports Outcome Predictor</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 700px; margin: 60px auto; padding: 20px; background: #f5f5f5; }
        h1 { color: #1a1a2e; }
        input, button { padding: 10px; margin: 8px 0; width: 100%; box-sizing: border-box; font-size: 16px; }
        button { background: #16213e; color: white; border: none; cursor: pointer; border-radius: 6px; }
        button:hover { background: #0f3460; }
        .result { background: white; padding: 20px; border-radius: 8px; margin-top: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .winner { font-size: 24px; font-weight: bold; color: #0f3460; }
        .confidence { color: #555; margin: 8px 0; }
        .reasoning { margin-top: 12px; line-height: 1.6; }
        .error { color: red; margin-top: 12px; }
        label { font-weight: bold; display: block; margin-top: 12px; }
    </style>
</head>
<body>
    <h1>⚽ AI Sports Outcome Predictor</h1>
    <p>Enter two teams to predict the likely winner using AI analysis.</p>

    <label>Team A ID (SportMonks)</label>
    <input type="number" id="team_a_id" placeholder="e.g. 85" />

    <label>Team A Name</label>
    <input type="text" id="team_a_name" placeholder="e.g. Manchester City" />

    <label>Team B ID (SportMonks)</label>
    <input type="number" id="team_b_id" placeholder="e.g. 86" />

    <label>Team B Name</label>
    <input type="text" id="team_b_name" placeholder="e.g. Arsenal" />

    <button onclick="predict()">Predict Winner</button>

    <div id="result"></div>

    <script>
        async function predict() {
            const team_a_id = parseInt(document.getElementById('team_a_id').value);
            const team_a_name = document.getElementById('team_a_name').value;
            const team_b_id = parseInt(document.getElementById('team_b_id').value);
            const team_b_name = document.getElementById('team_b_name').value;

            document.getElementById('result').innerHTML = '<p>Analyzing matchup...</p>';

            const response = await fetch('/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ team_a_id, team_a_name, team_b_id, team_b_name })
            });

            const data = await response.json();

            if (data.status === 'success') {
                document.getElementById('result').innerHTML = `
                    <div class="result">
                        <div class="winner">🏆 Predicted Winner: ${data.data.winner}</div>
                        <div class="confidence">Confidence: ${data.data.confidence}</div>
                        <div class="reasoning"><strong>Reasoning:</strong> ${data.data.reasoning}</div>
                    </div>`;
            } else {
                document.getElementById('result').innerHTML =
                    '<div class="error">Error: ' + (data.message || data.status) + '</div>';
            }
        }
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json()

    team_a_id = data.get("team_a_id")
    team_b_id = data.get("team_b_id")
    team_a_name = data.get("team_a_name", "Team A")
    team_b_name = data.get("team_b_name", "Team B")

    # Validate input
    if not team_a_id or not team_b_id:
        return jsonify({"status": "missing_team", "message": "Both team IDs are required"}), 400

    # Validate matchup via engine
    matchup = prepare_matchup(team_a_id, team_b_id)
    if matchup["status"] != "success":
        return jsonify(matchup), 400

    # Generate prediction via engine
    result = generate_prediction(team_a_id, team_b_id, team_a_name, team_b_name)
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
