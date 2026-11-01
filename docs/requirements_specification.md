# Requirements Specification

## AI Sports Outcome Predictor

**Course**: CS Final Project  
**Team**: SM Kamal, Brian Garcia  
**Date**: 2026-06-06

---

## Part A: Functionality

### Functionality 1: User Authentication

**Input:**
- Email address (string) and password (string) submitted via the login/sign-up form
- On protected requests: Firebase ID token passed as `Authorization: Bearer <token>` header

**Output:**
- Successful sign-in: Firebase ID token stored in client auth context; user redirected to `/dashboard`
- Successful sign-up: Account created, token issued, user redirected to `/dashboard`
- Backend token verification: decoded claims object `{uid, email, email_verified}`

**Success:**
- User enters valid credentials → Firebase returns an ID token → `AuthContext` stores the token → `ProtectedRoute` allows access to dashboard and prediction pages
- Every subsequent API call to a protected endpoint includes the token and receives a valid response

**Failure / Edge Cases:**
- Wrong password or unregistered email → Firebase returns an auth error → UI displays "Invalid credentials" message; user stays on auth page
- Expired token on a protected API call → backend returns HTTP 401 → frontend redirects user to login
- Missing or malformed `Authorization` header → backend returns HTTP 401 with message: "Missing or malformed Authorization header"

---

### Functionality 2: Fixture Discovery

**Input:**
- `GET /api/fixtures` (no authentication required)
- Implicit inputs: current date in America/Los_Angeles, FOOTBALL_DATA_API_KEY from environment

**Output:**
- JSON list of normalized fixture objects, each containing: `id`, `name`, `homeTeam {id, name, logo}`, `awayTeam {id, name, logo}`, `startingAt` (UTC string), `leagueId`, `leagueName`, `seasonId`, `status`, `venue`, `_isMock`
- `source` field indicating `"football-data"` (live data) or `"mock"` (fallback)

**Success:**
- football-data.org returns fixtures for the window (3 days back, 180 days ahead) per competition → backend normalizes and caches them → frontend groups them by day in LA time → fixture cards rendered grouped by league
- User can switch between Today and Tomorrow tabs; filter by league name; search by team name

**Failure / Edge Cases:**
- football-data.org API key missing → backend logs the error and returns demo fixtures with `source: "mock"`
- A competition has no upcoming fixtures (off-season) → the wide 180-day window still surfaces the next published fixtures; if every competition is empty, demo fixtures with dynamic today/tomorrow dates are returned instead
- football-data.org HTTP 403/429 (free-tier limit) → the cached fixture list is served if warm; if every competition fails → demo fixtures returned
- Backend unreachable from frontend → `catch` block in `fetchFixtures()` sets fixtures to `MOCK_FIXTURES` from `mockData.ts`; "Preview Data" badge shown

---

### Functionality 3: Match Prediction

**Input:**
- `POST /api/fixtures/{match_id}/prediction`
- `Authorization: Bearer <firebase_id_token>`
- `match_id`: fixture ID string (from fixture list)

**Output:**
- `winner`: predicted winning team name (string)
- `confidence`: `"low"` | `"medium"` | `"high"` (derived from Dixon-Coles winner probability)
- `home_win_probability`, `draw_probability`, `away_win_probability`: three-way floats in [0.05, 0.90]
- `probability_method`: always `"dixon-coles"`
- `reasoning`: 4–5 sentence natural-language explanation citing specific statistics (Gemini-generated)
- `keyFactors`: array of 3 objects `{title, text}` each citing a specific stat
- `headToHead`: historical W/D/L record and 5 most recent results between the two teams

**Success:**
- Backend resolves fixture → runs 7 parallel football-data.org enrichment calls → Dixon-Coles computes `{home_win, draw, away_win}` → winner determined → Gemini prompt constructed with DC winner + full enriched context → Gemini returns parsed response → DC winner and confidence override Gemini's qualitative labels → JSON returned to frontend → probability bar, verdict card, reasoning, and key factors rendered

**Failure / Edge Cases:**
- Fixture not in cache and not found on football-data.org → HTTP 404 "Fixture not found"
- `GEMINI_API_KEY` not set or engine import fails → HTTP 501 "Prediction engine unavailable"
- Individual enrichment calls fail (e.g., the football-data.org rate limit) → `_safe()` wrapper returns an error envelope; the section is listed in `missing_sections` and logged as `[Enrich] <section> unavailable …`; the Gemini prompt gets a DATA LIMITATIONS note naming it; neither the enrichment nor the prediction is cached
- Dixon-Coles returns `None` (insufficient stats data — e.g., team has 0 matches played) → HTTP 422 "Not enough data for a prediction"; Gemini is not called and the quota unit is refunded
- Prediction already cached for this matchup → returned without calling football-data.org or Gemini, and the quota unit is refunded; a user at their cap is still refused
- Gemini reports a server error (e.g. overloaded) → retried once after 2 seconds
- Gemini call still fails → HTTP 503 with a plain retry message; the quota unit is refunded and the raw error is logged

---

## Part B: Architecture Mapping

### Functionality 1 Mapping — User Authentication

**Interface responsibilities:**
- `src/app/auth/page.tsx`: renders email/password form; calls Firebase Auth SDK `signInWithEmailAndPassword` / `createUserWithEmailAndPassword`; handles error display
- `src/context/AuthContext.tsx`: listens to `onAuthStateChanged`; exposes `user` and `getIdToken()` to all components
- `src/components/ProtectedRoute.tsx`: redirects unauthenticated users to `/auth` before rendering any protected page, or to `/` straight after signing out
- `src/lib/api.ts` `authRequest()`: attaches `Authorization: Bearer <token>` header to all protected API calls

**Engine responsibilities:**
- `backend/firebase_config.py` `verify_id_token(token)`: calls Firebase Admin SDK to decode and validate the Bearer token on every protected endpoint
- `backend/main.py` `get_current_user()`: FastAPI dependency injected into all auth-required routes; raises HTTP 401 on missing, malformed, or invalid token

**Storage responsibilities:**
- Firebase Authentication service (Google-managed): stores user accounts, validates passwords, issues ID tokens with configurable expiry
- No local database table — identity is fully delegated to Firebase Auth

---

### Functionality 2 Mapping — Fixture Discovery

**Interface responsibilities:**
- `src/app/dashboard/page.tsx`: calls `getTopLeagueFixtures()` on mount; stores raw fixture list in state; applies date filter (`isUpcomingLocal()`), league filter, and search filter via `useMemo`; groups results by `leagueName`; renders `MatchCard` per fixture
- `src/lib/dateUtils.ts`: converts all `startingAt` UTC strings to the viewer's own time zone for filtering and display (DST-safe via `Intl.DateTimeFormat`)
- `src/lib/mockData.ts`: frontend-side fallback fixture list used when the backend is unreachable
- `src/components/FilterBar.tsx`: Today/Tomorrow tab, league dropdown, text search
- `src/components/MatchCard.tsx`: displays fixture card; links to `/prediction/[id]`

**Engine responsibilities:**
- `backend/main.py` `list_fixtures()`: serves a 5-minute TTL cache; otherwise calls `get_upcoming_fixtures()` and seeds `_fixture_cache`; falls back to demo fixtures with `source: "mock"`
- `storage/league_data_client.py` `_normalize_match()`: converts a raw football-data.org match into the frontend-compatible shape (`homeTeam`, `awayTeam`, `startingAt`, `leagueName`, `status`, `score`, `_isMock`)
- `backend/main.py` `_get_mock_fixtures()`: generates demo fixtures with dynamic today/tomorrow UTC kickoff times using `_mock_fixture_at()`

**Storage responsibilities:**
- `storage/league_data_client.py` `get_upcoming_fixtures()`: one `/competitions/{code}/matches` call per competition over a today−3 → today+180 window; keeps the soonest non-finished fixtures per competition; caches the merged list for 5 minutes (free tier is 10 requests/minute)

---

### Functionality 3 Mapping — Match Prediction

**Interface responsibilities:**
- `src/app/prediction/[matchId]/page.tsx`: calls `getFixtureById(matchId)` to display fixture info; on user action calls `generatePrediction(matchId, token)`; renders winner verdict, confidence badge, three-segment probability bar, reasoning text, key factors list, H2H record

**Engine responsibilities:**
- `backend/main.py` `fixture_prediction()`: resolves fixture from `_fixture_cache`; runs `_gather_enriched()` via `asyncio.gather` (7 parallel calls); calls `generate_prediction()` in a thread
- `engine/prediction_engine.py` `dixon_coles_probability()`: implements Dixon & Coles (1997) adjusted Poisson model with τ low-score correction and per-league home-advantage coefficients; returns `{home_win, draw, away_win}` in [0.05, 0.90]
- `engine/prediction_engine.py` `generate_prediction()`: fetches H2H via `compare_matchup()`; runs Dixon-Coles; builds structured Gemini prompt injecting DC winner and all enriched context; calls `gemini-2.5-flash` (no search grounding — the write-up uses only the prompt's data); parses structured response; overrides winner and confidence with DC values
- `engine/prediction_engine.py` `_build_enriched_section()`: formats enriched data (form, standings, xG, trends, injuries, lineups, top scorers, squad depth) into labeled prompt sections

**Storage responsibilities:**
- `storage/league_data_client.py`: provides all 7 enrichment functions — `get_fixtures_between_for_team()` (recent form), `get_season_standings()` (standings + team stats), `get_fixture_with_xg()` and `get_fixture_lineups()` (empty payloads — not on the free tier), `get_topscorers_with_names()` (top scorers), `get_squad()` (squad depth), `get_head_to_head()` (H2H history)

---

## Part C: Interface Contracts

### Functionality 1 — User Authentication

**interface → engine**

Function(s): `verify_id_token(token)` called via FastAPI dependency `get_current_user(authorization: str)`

Input payload:
```
Authorization: Bearer <firebase_id_token>
```

Return payload/status:
```json
{ "uid": "abc123", "email": "user@example.com", "email_verified": true }
```

Failure statuses:
- `HTTP 401` — "Missing or malformed Authorization header. Expected: Bearer \<token\>"
- `HTTP 401` — "Invalid or expired Firebase ID token."

**engine → storage**

Function(s): `firebase_admin.auth().verify_id_token(token)`

Input payload: Firebase ID token string

Return payload/status: Decoded claims dict `{uid, email, email_verified, iat, exp, ...}`

Failure statuses:
- `firebase_admin.auth.InvalidIdTokenError` → `verify_id_token()` returns `None` → caller raises HTTP 401
- `firebase_admin.auth.ExpiredIdTokenError` → same path → HTTP 401

---

### Functionality 2 — Fixture Discovery

**interface → engine**

Function(s): `getTopLeagueFixtures()` → `GET /api/fixtures`

Input payload: none

Return payload/status:
```json
{
  "status": "success",
  "source": "football-data | mock",
  "data": [ { "id": "…", "homeTeam": {…}, "awayTeam": {…}, "startingAt": "…", "leagueName": "…", "status": "NS", "_isMock": false } ]
}
```

Failure statuses:
- Network error (backend unreachable) → `catch` block → frontend uses `MOCK_FIXTURES` from `mockData.ts`
- `source: "mock"` with `_diagnostic` field → "Preview Data" badge shown; prediction pipeline still functional

**engine → storage**

Function(s): `get_upcoming_fixtures()`

Input payload: none (reads `FOOTBALL_DATA_API_KEY` from environment)

Return payload/status:
```json
{ "status": "success", "data": [ <normalized fixture dicts> ], "source": "football-data" }
```

Failure statuses:
- `{"status": "error", "message": "FOOTBALL_DATA_API_KEY is not set…"}` → mock fallback
- `{"status": "error", "message": "HTTP 403 Forbidden…"}` → cached list served when warm
- All strategies return empty → `{"status": "error", "message": "…0 fixtures…"}` → mock fallback

---

### Functionality 3 — Match Prediction

**interface → engine**

Function(s): `generatePrediction(matchId, token)` → `POST /api/fixtures/{match_id}/prediction`

Input payload:
```
POST /api/fixtures/19284651/prediction
Authorization: Bearer <firebase_id_token>
```

Return payload/status:
```json
{
  "status": "success",
  "data": {
    "winner": "Inter Miami CF",
    "confidence": "high",
    "reasoning": "Inter Miami CF averages 1.82 goals per game…",
    "home_win_probability": 0.58,
    "draw_probability": 0.22,
    "away_win_probability": 0.20,
    "probability_method": "dixon-coles",
    "headToHead": { "teamAWins": 3, "teamBWins": 1, "draws": 1, "total": 5, "recentResults": […] },
    "keyFactors": [ { "title": "Attacking Output", "text": "…" }, … ]
  }
}
```

Failure statuses:
- `HTTP 401` — invalid or missing token
- `HTTP 403` — email not verified, or signed-in account is not on the `ALLOWED_EMAILS` allowlist
- `HTTP 429` — per-user or shared daily prediction cap reached (resets 00:00 UTC)
- `HTTP 503` — daily counts unreachable in Firestore, so the prediction is refused rather than run uncounted (owners are unaffected); or the prediction engine failed, in which case the unit is refunded and the raw reason is logged as `[Predict] …`
- `HTTP 404` — fixture not found in cache or on football-data.org
- `HTTP 501` — "Prediction engine unavailable — GEMINI_API_KEY may not be set"

**engine → storage**

Function(s): 7 football-data.org calls via `_gather_enriched()` (all wrapped in `_safe()`):
- `get_fixtures_between_for_team(team_id, start, end, 5)`
- `get_season_standings(season_id)`
- `get_fixture_with_xg(fixture_id)`
- `get_fixture_lineups(fixture_id, team_a_id, team_b_id)`
- `get_topscorers_with_names(season_id, 10)`
- `get_squad(team_a_id)`
- `get_head_to_head(team_a_id, team_b_id)` (called separately in `compare_matchup`)

Input payload: team IDs (int), season ID (int | None), fixture ID (int), date range strings

Return payload/status:
```json
{ "status": "success", "data": <list or dict depending on endpoint> }
```

Failure statuses:
- Any single call returns `{"status": "error", "message": "…"}` or raises exception → `_safe()` returns `None` → that enrichment section omitted from Gemini prompt; pipeline continues
- All enrichment calls fail → `enriched_data` is `None` → Dixon-Coles returns `None` → HTTP 422 "Not enough data for a prediction", no Gemini call

---

