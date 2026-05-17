"use client";

import ProtectedRoute from "@/components/ProtectedRoute";
import { useAuth } from "@/context/AuthContext";

/**
 * /dashboard — protected page.
 * Placeholder only; final design will be applied later.
 */
export default function DashboardPage() {
  const { user, logout } = useAuth();

  return (
    <ProtectedRoute>
      <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-gray-500">
          Placeholder dashboard — final design coming soon.
        </p>
        {user && (
          <p className="text-sm text-gray-400">Signed in as {user.email}</p>
        )}
        <button
          onClick={logout}
          className="rounded border px-4 py-2 text-sm hover:bg-gray-50"
        >
          Sign out
        </button>
      </main>
    </ProtectedRoute>
  );
}
