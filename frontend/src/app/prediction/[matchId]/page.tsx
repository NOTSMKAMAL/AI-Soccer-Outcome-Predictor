"use client";

import ProtectedRoute from "@/components/ProtectedRoute";

/**
 * /prediction/[matchId] — protected dynamic route.
 * Placeholder only; final design and data fetching will be added later.
 */
export default function PredictionPage({
  params,
}: {
  params: { matchId: string };
}) {
  return (
    <ProtectedRoute>
      <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
        <h1 className="text-3xl font-bold">Match Prediction</h1>
        <p className="text-gray-500">
          Placeholder prediction page — final design coming soon.
        </p>
        <p className="font-mono text-sm text-gray-400">
          matchId: {params.matchId}
        </p>
      </main>
    </ProtectedRoute>
  );
}
