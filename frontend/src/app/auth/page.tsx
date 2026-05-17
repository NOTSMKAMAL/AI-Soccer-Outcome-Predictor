"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

/**
 * /auth — sign in / sign up page.
 * Placeholder layout only; final design will be applied later.
 * Redirects authenticated users to /dashboard.
 */
export default function AuthPage() {
  const { user, loading, signIn, signUp, signInWithGoogle } = useAuth();
  const router = useRouter();

  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && user) {
      router.replace("/dashboard");
    }
  }, [user, loading, router]);

  // Don't flash the form while checking auth state or after redirect
  if (loading || user) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (isSignUp) {
        await signUp(email, password);
      } else {
        await signIn(email, password);
      }
      router.replace("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
    } finally {
      setBusy(false);
    }
  };

  const handleGoogle = async () => {
    setError("");
    setBusy(true);
    try {
      await signInWithGoogle();
      router.replace("/dashboard");
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Google sign-in failed."
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-2xl font-bold">
        {isSignUp ? "Create account" : "Sign in"}
      </h1>

      <form
        onSubmit={handleSubmit}
        className="flex w-full max-w-sm flex-col gap-3"
      >
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
          required
          className="rounded border px-3 py-2"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          required
          className="rounded border px-3 py-2"
        />
        <button
          type="submit"
          disabled={busy}
          className="rounded bg-indigo-600 py-2 text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {isSignUp ? "Create account" : "Sign in"}
        </button>
      </form>

      <button
        onClick={handleGoogle}
        disabled={busy}
        className="rounded border px-4 py-2 hover:bg-gray-50 disabled:opacity-50"
      >
        Continue with Google
      </button>

      <button
        onClick={() => setIsSignUp((v) => !v)}
        className="text-sm text-indigo-600 hover:underline"
      >
        {isSignUp
          ? "Already have an account? Sign in"
          : "No account? Create one"}
      </button>

      {error && <p className="text-sm text-red-600">{error}</p>}
    </main>
  );
}
