const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ── Internal helpers ──────────────────────────────────────────────────────────

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

async function authRequest<T>(
  path: string,
  token: string,
  options?: RequestInit
): Promise<T> {
  return request<T>(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options?.headers ?? {}),
    },
  });
}

// ── Public endpoints (no auth required) ──────────────────────────────────────

/** Returns the list of supported teams from the backend. */
export async function getTeams() {
  return request<{ status: string; data: unknown[] }>("/api/teams");
}

/**
 * Returns upcoming fixtures for top leagues.
 * Backed by GET /api/fixtures — wired to storage/sportmonks_client.py
 * once the main-branch engine/storage layer is merged into this branch.
 */
export async function getTopLeagueFixtures() {
  return request<{ status: string; data: unknown[] }>("/api/fixtures");
}

/**
 * Returns a single fixture by ID.
 * Backed by GET /api/fixtures/{matchId} — wired to storage/sportmonks_client.py
 * once the main-branch engine/storage layer is merged.
 */
export async function getFixtureById(matchId: string) {
  return request<{ status: string; data: unknown }>(
    `/api/fixtures/${matchId}`
  );
}

// ── Protected endpoints (Firebase ID token required) ─────────────────────────

/**
 * Triggers a prediction for the given fixture.
 * Backed by POST /api/fixtures/{matchId}/prediction — wired to
 * engine/prediction_engine.py once the main-branch layer is merged.
 */
export async function generatePrediction(matchId: string, token: string) {
  return authRequest<{ status: string; data: unknown }>(
    `/api/fixtures/${matchId}/prediction`,
    token,
    { method: "POST" }
  );
}

/** Fetches the authenticated user's saved prediction history. */
export async function getUserPredictions(token: string) {
  return authRequest<{ status: string; data: unknown[] }>(
    "/api/predictions",
    token
  );
}

/** Persists a prediction result to the user's Firestore history. */
export async function saveUserPrediction(
  token: string,
  payload: Record<string, unknown>
) {
  return authRequest<{ status: string; data: { id: string } }>(
    "/api/predictions",
    token,
    { method: "POST", body: JSON.stringify(payload) }
  );
}

/** Removes a saved prediction by its Firestore document ID. */
export async function deleteUserPrediction(
  token: string,
  predictionId: string
) {
  return authRequest<{ status: string; data: { id: string } }>(
    `/api/predictions/${predictionId}`,
    token,
    { method: "DELETE" }
  );
}
