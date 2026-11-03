/**
 * Server-side half of the prediction proxy. Import it only from a route handler:
 * the shared secret must never reach the browser.
 *
 * Vercel sets x-vercel-ip-country on requests to its functions. The API can't see
 * that itself, so this passes the country on with a secret the API checks, and
 * builds the headers from scratch so a visitor can't supply their own.
 */

interface ProxyOptions {
  apiBase: string;
  gateSecret?: string;
  fetchImpl?: typeof fetch;
}

export async function forwardPrediction(
  request: Request,
  matchId: string,
  { apiBase, gateSecret, fetchImpl = fetch }: ProxyOptions,
): Promise<Response> {
  const headers: Record<string, string> = {};
  const authorization = request.headers.get("authorization");
  const country = request.headers.get("x-vercel-ip-country");
  if (authorization) headers["Authorization"] = authorization;
  if (country) headers["X-Visitor-Country"] = country;
  if (gateSecret) headers["X-Geo-Gate-Secret"] = gateSecret;

  try {
    const upstream = await fetchImpl(
      `${apiBase}/api/fixtures/${encodeURIComponent(matchId)}/prediction`,
      { method: "POST", headers, cache: "no-store" },
    );
    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return Response.json(
      { detail: "We can't reach the prediction server. Try again in a minute." },
      { status: 502 },
    );
  }
}
