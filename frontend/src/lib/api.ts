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

// Session cache: resets on page reload. Max staleness: 5 minutes.
// To force a refresh during demo, reload the page.
let _fixturesCache: { data: unknown[]; ts: number } | null = null;
const FIXTURES_TTL_MS = 5 * 60 * 1000;

export async function getTopLeagueFixtures() {
  const now = Date.now();
  if (_fixturesCache && now - _fixturesCache.ts < FIXTURES_TTL_MS) {
    return { status: "success", data: _fixturesCache.data, source: "cache" };
  }
  const result = await request<{ status: string; data: unknown[] }>("/api/fixtures");
  if (result.data?.length) {
    _fixturesCache = { data: result.data, ts: now };
  }
  return result;
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
