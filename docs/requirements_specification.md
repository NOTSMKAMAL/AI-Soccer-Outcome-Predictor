# Requirements Specification

## AI Sports Outcome Predictor

**Course**: CS Final Project  
**Team**: SM Kamal, Brian Garcia  
**Date**: 2026-05-16

---

## 1. Project Overview

The AI Sports Outcome Predictor is a web-based application that uses machine learning and statistical analysis to forecast the outcomes of international soccer matches. Users select two competing national teams and receive a prediction that includes a winner, confidence percentage, and a breakdown of key performance metrics.

---

## 2. Functional Requirements

### 2.1 Team Selection

- The system shall present a list of available international soccer teams retrieved from the API-Football data source.
- Users shall be able to select exactly two distinct teams (Team A and Team B) via dropdown menus.
- The interface shall prevent users from selecting the same team for both slots.
- The system shall display team metadata (name, country) alongside each selection.
- Team data shall be cached in Supabase to reduce redundant API calls.

### 2.2 Match Prediction

- Upon submitting a valid team pair, the system shall invoke the AI prediction engine.
- The prediction engine shall analyze the following statistical dimensions:
  - **Attack strength**: Goal-scoring rate and offensive efficiency (scale 0–10)
  - **Defensive strength**: Goals conceded rate and defensive solidity (scale 0–10)
  - **Recent form**: Win/draw/loss record across the last 5 matches (scale 0–5)
- The system shall determine a predicted winner based on weighted statistical comparison.
- The system shall compute a confidence score (0–100%) reflecting the margin of statistical advantage.
- Predictions shall be enriched by a Google Gemini LLM agent that generates a natural-language reasoning summary.
- All predictions shall be persisted in Supabase for audit and caching purposes.

### 2.3 Results Display

- The system shall display the predicted winner prominently with the confidence percentage.
- The system shall render the AI-generated reasoning text explaining the prediction rationale.
- The system shall present a visual comparison chart (bar chart) contrasting both teams across attack, defense, and recent form dimensions.
- Users shall be able to navigate back to the team selection screen to run a new prediction.
- The system shall handle and display errors gracefully when backend services are unavailable, falling back to mock data.

---

## 3. Non-Functional Requirements

### 3.1 Performance
- Team list retrieval shall respond within 2 seconds under normal conditions.
- Prediction generation shall complete within 10 seconds end-to-end.

### 3.2 Reliability
- The application shall remain functional with mock data when external APIs (API-Football, Supabase, Gemini) are unavailable.
- All external API calls shall include error handling with informative user-facing messages.

### 3.3 Usability
- The interface shall be navigable without documentation by a non-technical user.
- Prediction results shall be presented in plain language, not raw JSON.

### 3.4 Maintainability
- Backend logic shall be separated into single-responsibility modules (predictor, agent, soccer_api, supabase_db).
- Frontend components shall be reusable across pages.

---

## 4. External Integrations

| Service | Purpose | Fallback |
|---------|---------|---------|
| API-Football | Live team and match statistics | Mock team and stats data |
| Google Gemini | Natural-language reasoning | Rule-based reasoning text |
| Supabase | Prediction cache and team cache | In-memory (no persistence) |

---

## 5. Constraints

- The application is scoped to international national teams only (no club teams).
- Predictions are probabilistic estimates, not guarantees; a disclaimer shall be displayed.
- The Gemini API free tier rate limit applies; heavy concurrent use may trigger throttling.
