## Data sources

- **football-data.org v4** — the only live football data source (fixtures, standings,
  form, scorers). Free tier: 10 requests/minute, so every call is cached AND
  self-throttled: `storage/_fdorg.py` reads the `X-RequestsAvailable` /
  `X-RequestCounter-Reset` response headers and will not send a request while the
  budget is spent (the provider asks clients to do this). Never bypass `_fdorg.get()`.
  Docs: https://www.football-data.org/documentation/quickstart
  Client: `storage/league_data_client.py` (HTTP layer in `storage/_fdorg.py`).
  Not on the free tier: xG, lineups, injuries — those helpers return empty payloads
  on purpose and the prompt omits the section.
- **Gemini** (`google-genai`, model `gemini-2.5-flash`) — reasoning only, never the
  probabilities. Called from `engine/prediction_engine.py`.

## Rules

- Only `POST /api/fixtures/{id}/prediction` may spend Gemini credit, and it must stay
  behind `backend/access.py` (Firebase auth + allowlist + daily quota).
- Probabilities come from Dixon-Coles; Gemini's winner/confidence is overridden by the
  model output, never the other way round.
- Any accuracy figure quoted must be the point-in-time backtest number
  (`python scripts/backtest.py`), never the `--leaky` contrast run.
