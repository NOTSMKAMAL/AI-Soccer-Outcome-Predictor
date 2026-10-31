"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import PageLoading from "@/components/PageLoading";

interface Props {
  children: React.ReactNode;
}

/**
 * Wraps any page that requires authentication.
 * - While auth state is being resolved: renders a neutral loading state.
 * - If unauthenticated: redirects to /auth, or to the landing page straight
 *   after signing out, so Back can't reach protected content.
 * - If authenticated: renders children.
 */
export default function ProtectedRoute({ children }: Props) {
  const { user, loading, signedOut } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace(signedOut ? "/" : "/auth");
    }
  }, [user, loading, signedOut, router]);

  if (loading) return <PageLoading />;

  if (!user) return null;

  return <>{children}</>;
}
