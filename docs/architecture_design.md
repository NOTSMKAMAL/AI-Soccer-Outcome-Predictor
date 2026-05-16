# Architecture Design

## AI Sports Outcome Predictor

**Version**: 1.0  
**Date**: 2026-05-16

---

## 1. System Overview

The application follows a three-layer architecture separating user interaction, prediction logic, and data storage. Communication between the frontend and backend occurs over a REST API. The AI agent runs inside the backend process and orchestrates all external service calls.

```
┌─────────────────────────────────────────────────┐
│                 Interface Layer                  │
│           Streamlit Multi-Page App               │
│  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ Team Select  │  │   Prediction Results     │ │
│  │   Page       │  │         Page             │ │
│  └──────┬───────┘  └───────────┬──────────────┘ │
│         │   frontend/          │                 │
│         └──────────┬───────────┘                 │
│              api_client.py                       │
└──────────────────┬──────────────────────────────┘
                   │  HTTP (REST)
┌──────────────────▼──────────────────────────────┐
│                 Engine Layer                     │
│              FastAPI Backend                     │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ main.py  │  │ agent.py │  │ predictor.py  │  │
│  │ (routes) │→ │(LangGraph│→ │  (stats)      │  │
│  └──────────┘  │ workflow)│  └───────────────┘  │
│                └────┬─────┘                     │
│                     │                           │
│         ┌───────────▼───────────┐               │
│         │     soccer_api.py     │               │
│         │  (API-Football client)│               │
│         └───────────────────────┘               │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│                Storage Layer                     │
│  ┌───────────────────────┐  ┌─────────────────┐ │
│  │     Supabase DB       │  │  API-Football   │ │
│  │  supabase_db.py       │  │  External API   │ │
│  │  - predictions cache  │  │  - team stats   │ │
│  │  - team cache         │  │  - match history│ │
│  └───────────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────┘
```

---

## 2. Layer Descriptions

### 2.1 Interface Layer

**Technology**: Streamlit 1.31

The frontend is a Streamlit multi-page application. Each page is a self-contained Python script in `frontend/pages/`. Shared UI components live in `frontend/components/` and are imported by pages as needed.

| File | Responsibility |
|------|---------------|
| `app.py` | Landing page, navigation entrypoint |
| `pages/1_team_select.py` | Team selection form and submission |
| `pages/2_prediction.py` | Results display (winner, confidence, charts) |
| `components/team_selector.py` | Reusable team dropdown widget |
| `components/prediction_card.py` | Styled prediction result card |
| `components/comparison_chart.py` | Plotly bar chart for stat comparison |
| `api_client.py` | HTTP client wrapping all backend calls |

The frontend communicates with the backend exclusively through `api_client.py`, which issues HTTP requests to the FastAPI server. If the backend is unreachable, `api_client.py` returns mock data so the UI remains functional.

### 2.2 Engine Layer

**Technology**: FastAPI 0.109, LangGraph 0.0.20, Google Gemini

The backend exposes a REST API and hosts the AI prediction workflow.

| File | Responsibility |
|------|---------------|
| `main.py` | FastAPI app, CORS config, route definitions |
| `agent.py` | LangGraph state machine orchestrating the prediction |
| `predictor.py` | Statistical comparison and confidence calculation |
| `soccer_api.py` | API-Football HTTP wrapper |
| `supabase_db.py` | Supabase read/write helpers |
| `config.py` | Environment variable loading via python-dotenv |

**Prediction workflow** (LangGraph nodes):

```
START → fetch_team_stats → compute_prediction → enrich_with_llm → cache_result → END
```

1. `fetch_team_stats`: Calls `soccer_api.py` (or returns cached stats from Supabase).
2. `compute_prediction`: Runs `predictor.py` to produce a winner and confidence score.
3. `enrich_with_llm`: Sends stats + prediction to Gemini for a reasoning narrative.
4. `cache_result`: Persists the final prediction to Supabase via `supabase_db.py`.

### 2.3 Storage Layer

**Technology**: Supabase (PostgreSQL), API-Football

| Store | Schema | TTL |
|-------|--------|-----|
| `predictions` table | `team_a_id`, `team_b_id`, `winner`, `confidence`, `reasoning`, `created_at` | 24 hours |
| `team_stats` table | `team_id`, `attack`, `defense`, `form`, `fetched_at` | 6 hours |

---

## 3. Data Flow

### Team List Request

```
Browser → Streamlit → api_client.GET /api/teams → FastAPI → soccer_api → API-Football
                                                                        ↓ (miss)
                                                            Supabase team cache (hit)
```

### Prediction Request

```
Browser → Streamlit → api_client.POST /api/predict
                                │
                         FastAPI main.py
                                │
                          agent.py (LangGraph)
                         ┌──────┴──────┐
                    soccer_api    supabase_db (cache check)
                         │
                    predictor.py (stats comparison)
                         │
                    Gemini LLM (reasoning text)
                         │
                    supabase_db (persist result)
                         │
                    JSON response → Streamlit → Display
```

---

## 4. API Contract

### GET /api/teams

Response:
```json
{
  "status": "success",
  "data": [
    {"id": 33, "name": "Argentina", "country": "Argentina"},
    {"id": 2, "name": "France", "country": "France"}
  ]
}
```

### POST /api/predict

Request:
```json
{"team_a_id": 33, "team_b_id": 2}
```

Response:
```json
{
  "status": "success",
  "data": {
    "teams": {
      "team_a": {"id": 33, "name": "Argentina"},
      "team_b": {"id": 2, "name": "France"}
    },
    "winner": "Argentina",
    "confidence": 72,
    "reasoning": "...",
    "comparison": {
      "attack":      {"argentina": 8.5, "france": 7.8},
      "defense":     {"argentina": 8.1, "france": 8.3},
      "recent_form": {"argentina": 4.2, "france": 3.6}
    }
  }
}
```

---

## 5. Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Frontend framework | Streamlit | Rapid prototyping; built-in multi-page routing |
| Backend framework | FastAPI | Async support; automatic OpenAPI docs |
| AI orchestration | LangGraph | Explicit state machine; easy to extend nodes |
| LLM provider | Google Gemini | Free tier; strong multilingual reasoning |
| Database | Supabase | Managed Postgres; Python SDK; free tier |
| Charting | Plotly | Interactive charts; Streamlit native integration |
