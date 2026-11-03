import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { forwardPrediction } from "../src/lib/predictionProxy.ts";

const API = "https://api.example.com";
const SECRET = "test-gate-secret";

function visitor(headers = {}) {
  return new Request("https://site.example.com/api/fixtures/42/prediction", { method: "POST", headers });
}

/** A stand-in for the API that records what it was sent. */
function fakeApi(status = 200, body = '{"status":"success"}') {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, headers: new Headers(init.headers), method: init.method });
    return new Response(body, { status, headers: { "Content-Type": "application/json" } });
  };
  return { calls, fetchImpl };
}

describe("what the proxy sends to the API", () => {
  it("passes on the sign-in token, Vercel's country and the secret", async () => {
    const api = fakeApi();
    await forwardPrediction(
      visitor({ authorization: "Bearer token", "x-vercel-ip-country": "DE" }),
      "42",
      { apiBase: API, gateSecret: SECRET, fetchImpl: api.fetchImpl },
    );
    const [call] = api.calls;
    assert.equal(call.method, "POST");
    assert.equal(call.url, `${API}/api/fixtures/42/prediction`);
    assert.equal(call.headers.get("authorization"), "Bearer token");
    assert.equal(call.headers.get("x-visitor-country"), "DE");
    assert.equal(call.headers.get("x-geo-gate-secret"), SECRET);
  });

  it("sends no country when Vercel gave none, so the API refuses", async () => {
    const api = fakeApi();
    await forwardPrediction(visitor(), "42", { apiBase: API, gateSecret: SECRET, fetchImpl: api.fetchImpl });
    assert.equal(api.calls[0].headers.has("x-visitor-country"), false);
  });

  it("ignores a country or secret the visitor sends themselves", async () => {
    const api = fakeApi();
    await forwardPrediction(
      visitor({ "x-visitor-country": "US", "x-geo-gate-secret": "guess" }),
      "42",
      { apiBase: API, gateSecret: SECRET, fetchImpl: api.fetchImpl },
    );
    const [call] = api.calls;
    assert.equal(call.headers.has("x-visitor-country"), false);
    assert.equal(call.headers.get("x-geo-gate-secret"), SECRET);
  });

  it("forwards nothing else from the visitor", async () => {
    const api = fakeApi();
    await forwardPrediction(
      visitor({ cookie: "a=b", "x-forwarded-for": "1.2.3.4" }),
      "42",
      { apiBase: API, gateSecret: SECRET, fetchImpl: api.fetchImpl },
    );
    assert.equal(api.calls[0].headers.has("cookie"), false);
    assert.equal(api.calls[0].headers.has("x-forwarded-for"), false);
  });

  it("works locally with no secret and no country", async () => {
    const api = fakeApi();
    const response = await forwardPrediction(visitor(), "42", { apiBase: API, fetchImpl: api.fetchImpl });
    assert.equal(api.calls[0].headers.has("x-geo-gate-secret"), false);
    assert.equal(response.status, 200);
  });

  it("can't be sent to another path by a crafted match id", async () => {
    const api = fakeApi();
    await forwardPrediction(visitor(), "../../me", { apiBase: API, fetchImpl: api.fetchImpl });
    assert.equal(api.calls[0].url, `${API}/api/fixtures/..%2F..%2Fme/prediction`);
  });
});

describe("what the visitor gets back", () => {
  it("is the API's answer", async () => {
    const api = fakeApi(200, '{"status":"success","data":{"winner":"Home"}}');
    const response = await forwardPrediction(visitor(), "42", { apiBase: API, fetchImpl: api.fetchImpl });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { status: "success", data: { winner: "Home" } });
  });

  it("keeps the API's status and reason when a region is refused", async () => {
    const api = fakeApi(451, '{"detail":"AI predictions aren\'t available"}');
    const response = await forwardPrediction(visitor(), "42", { apiBase: API, fetchImpl: api.fetchImpl });
    assert.equal(response.status, 451);
    assert.equal((await response.json()).detail, "AI predictions aren't available");
  });

  it("is a clear message when the API can't be reached", async () => {
    const fetchImpl = async () => { throw new TypeError("fetch failed"); };
    const response = await forwardPrediction(visitor(), "42", { apiBase: API, fetchImpl });
    assert.equal(response.status, 502);
    assert.match((await response.json()).detail, /Try again/);
  });

  it("never includes the secret", async () => {
    const api = fakeApi();
    const response = await forwardPrediction(visitor(), "42", { apiBase: API, gateSecret: SECRET, fetchImpl: api.fetchImpl });
    assert.equal((await response.text()).includes(SECRET), false);
    assert.equal([...response.headers.values()].includes(SECRET), false);
  });
});
