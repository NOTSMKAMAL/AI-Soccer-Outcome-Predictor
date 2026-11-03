# AI Sports Outcome Predictor

Predicts football match outcomes by combining a **Dixon-Coles statistical model** with
**Gemini** reasoning: the model produces the probabilities, Gemini explains them. Live
fixtures, form and standings come from the free tier of **football-data.org**.

**Stack:** Next.js 14 + TypeScript (frontend) · FastAPI (API) · Firebase Auth · Firestore
(daily limits) · SQLite (prediction history) · Gemini 2.5 Flash.

Originally built for CS180 by SM Kamal and Brian Garcia.

---

## What it does

- **Fixture discovery** — upcoming matches across the Premier League, Bundesliga,
  La Liga, Serie A, Ligue 1 and the Champions League, grouped by day and league.
- **Match prediction** — a three-way probability (home / draw / away) from Dixon-Coles,
  a confidence label derived from that probability, and a written rationale from Gemini
  built on recent form, standings and top scorers. Head-to-head records, injuries, lineups
  and xG aren't on football-data.org's free tier, so predictions don't use them.
- **Honest evaluation** — every prediction is stored, resolved against the real result
  once the match finishes, and scored (accuracy / Brier / log-loss / ECE / reliability)
  through `/api/analytics`.
- **Offline backtest** — `scripts/backtest.py` re-runs the model over 1,526 historical
  fixtures with no lookahead, so a model change can be checked for regressions.

### How good is it, honestly

From the point-in-time backtest (`python scripts/backtest.py`, no lookahead):

| Metric | Value |
|---|---|
| Accuracy | **48.4%** (±2.5% at 95% CI, n=1,526) |
| Always-pick-home baseline | 44.3% |
| Accuracy when confidence is "high" (≥65%) | 59.3% (n=344) |
| Brier score / log loss | 0.635 / 1.059 |

Football is genuinely hard to predict; the model beats the home-team baseline by about
4 points and its confidence label carries real signal, and that is the claim it makes.
The `--leaky` mode reproduces the flattering 52.8% number that end-of-season
aggregates produce, purely as a contrast.

---

## Source code

| Layer | Path |
|---|---|
| Frontend (Next.js) | [`frontend/src/`](frontend/src/) |
| API (FastAPI) | [`backend/`](backend/) |
| Prediction engine (Dixon-Coles + Gemini) | [`engine/`](engine/) |
| Data clients + prediction store | [`storage/`](storage/) |
| Offline evaluation | [`scripts/`](scripts/) |

### API endpoints

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/health` | — | status + today's quota usage |
| GET | `/api/fixtures` | — | upcoming fixtures (cached 5 min) |
| GET | `/api/fixtures/{id}` | — | single fixture |
| POST | `/api/fixtures/{id}/prediction` | Firebase | **the only endpoint that spends Gemini credit** |
| GET | `/api/fixtures/{id}/enriched` | Firebase | form / standings / stats used by the prompt |
| GET | `/api/me/prediction-allowance` | Firebase | predictions left today, or unlimited for owners |
| DELETE | `/api/me` | Firebase, recent sign-in | deletes the user's quota counters and Firebase account |
| POST | `/api/auth/verify` | Firebase | token check |
| GET | `/api/analytics` | — | accuracy, reliability bins, over-time series |
| GET | `/api/analytics/calibration` | — | accuracy / Brier / log-loss / ECE |
| GET | `/api/analytics/betting` | — | ROI / win-rate / edge (empty without market data) |
| GET | `/api/predictions/{id}/history` | — | stored predictions for a match |

---

## Tests

```bash
pytest tests/
```

| File | What it covers |
|---|---|
| [`tests/test_prediction_engine.py`](tests/test_prediction_engine.py) | Dixon-Coles math, confidence labels, winner logic, edge cases, backtest regression invariants |
| [`tests/test_league_data_client.py`](tests/test_league_data_client.py) | football-data.org client (mocked HTTP, normalization, graceful failure) |
| [`tests/test_access.py`](tests/test_access.py) | verified email, owner bypass, allowlist, per-user and global daily quota, refund, day rollover (fake Firestore) |
| [`tests/test_access_firestore_sdk.py`](tests/test_access_firestore_sdk.py) | the quota against the real Firestore SDK with its network layer mocked |
| [`tests/test_main_prediction_access.py`](tests/test_main_prediction_access.py) | the prediction route's gate and refund-on-failure wiring |
| [`tests/test_main_account.py`](tests/test_main_account.py) | account deletion: recent sign-in rule and step order |
| [`tests/test_main_enrichment.py`](tests/test_main_enrichment.py) | shared enrichment gather, failed-section reporting, cache expiry |
| [`tests/test_firebase_config.py`](tests/test_firebase_config.py) | Firebase token check: clock skew and failure logging |
| [`tests/test_prediction_db.py`](tests/test_prediction_db.py) | SQLite prediction store (upsert, resolve, read) |
| [`tests/test_scoring_confidence_signal.py`](tests/test_scoring_confidence_signal.py) | shared confidence / risk / value-signal scoring |

---

## Demo video

https://www.youtube.com/watch?v=s4UfIk_ctJw

---

## Documentation

- [`docs/prediction_pipeline.md`](docs/prediction_pipeline.md) — end-to-end walkthrough:
  fixture → enrichment → Dixon-Coles → Gemini → response, plus the accuracy analysis.
- [`docs/requirements_specification.md`](docs/requirements_specification.md) — inputs,
  outputs, failure cases and interface contracts per functionality.
- [`DEPLOY.md`](DEPLOY.md) — putting it online publicly without running up a Gemini
  bill, including the Firestore setup the daily caps need.

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+

### 1. Clone

```bash
git clone https://github.com/NOTSMKAMAL/AI-Soccer-Outcome-Predictor.git
cd AI-Soccer-Outcome-Predictor
```

### 2. Backend

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

| Variable | Where to get it |
|---|---|
| `GEMINI_API_KEY` | https://aistudio.google.com → Get API key (free tier) |
| `FOOTBALL_DATA_API_KEY` | https://www.football-data.org/client/register (free tier) |
| `FIREBASE_SERVICE_ACCOUNT_PATH` | Firebase Console → Project Settings → Service Accounts → Generate new private key → save as `serviceAccountKey.json` in the project root |

Predicting needs a Firestore database in your Firebase project, because the daily
counts live there. Owners are the exception. See Step 1 of [`DEPLOY.md`](DEPLOY.md).

Optional but recommended before sharing a link:

| Variable | Effect |
|---|---|
| `OWNER_EMAILS` | exact, verified emails that skip the allowlist and both caps |
| `ALLOWED_EMAILS` | only these accounts may generate predictions (empty = any verified user) |
| `PREDICTIONS_PER_USER_PER_DAY` | per-account daily cap (default 3; 0 blocks everyone but owners) |
| `PREDICTIONS_PER_DAY_TOTAL` | shared daily cap across all users (default 50; 0 blocks everyone but owners) |
| `ALLOWED_ORIGINS` | browser origins allowed to call the API |
| `GEO_GATE_SECRET` | production only: shared with Vercel so the API can trust the visitor's country. Leave unset locally |

Start it:

```bash
uvicorn backend.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
```

Fill `frontend/.env.local` with your Firebase web-app config (Firebase Console →
Project Settings → Your apps → SDK setup) and `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`.

```bash
npm run dev
```

Open http://localhost:3000.

### 4. Running both

Two terminals — backend (`uvicorn backend.main:app --reload --port 8000`) and frontend
(`cd frontend && npm run dev`).

Without API keys the app still runs: the dashboard serves mock fixtures marked as
preview data, and predictions are disabled for them.

---

## Offline evaluation

```bash
python scripts/backtest.py            # point-in-time — the honest baseline
python scripts/backtest.py --leaky    # lookahead contrast, for comparison only
```

Results are written to `scripts/data/backtest_csv_results.json`, which
`tests/test_prediction_engine.py` asserts against as a regression baseline.
