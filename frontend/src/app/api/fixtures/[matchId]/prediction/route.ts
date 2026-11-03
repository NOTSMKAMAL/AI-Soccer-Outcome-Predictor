import { forwardPrediction } from "@/lib/predictionProxy";

// Long enough for a sleeping API instance to wake and Gemini to finish.
export const maxDuration = 120;

/** Sends a prediction to the API with the visitor's country, so the API can enforce the region gate. */
export async function POST(request: Request, { params }: { params: { matchId: string } }) {
  return forwardPrediction(request, params.matchId, {
    apiBase: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
    gateSecret: process.env.GEO_GATE_SECRET,
  });
}
