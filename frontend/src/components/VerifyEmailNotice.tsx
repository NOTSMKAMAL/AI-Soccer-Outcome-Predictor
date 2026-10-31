"use client";

import { useState } from "react";
import { useAuth } from "@/context/AuthContext";

type Status = { tone: "info" | "warn"; text: string } | null;

const TOO_MANY_REQUESTS = "auth/too-many-requests";

/** Replaces the predict button until the signed-in account's email is verified. */
export default function VerifyEmailNotice() {
  const { user, resendVerificationEmail, refreshEmailVerified } = useAuth();
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<Status>(null);

  const run = async (action: () => Promise<Status>) => {
    setBusy(true);
    setStatus(null);
    try {
      setStatus(await action());
    } catch (err: unknown) {
      const code = (err as { code?: string })?.code;
      setStatus({
        tone: "warn",
        text: code === TOO_MANY_REQUESTS
          ? "Too many attempts. Wait a few minutes and try again."
          : "That didn't work. Check your connection and try again.",
      });
    } finally {
      setBusy(false);
    }
  };

  const resend = () => run(async () => {
    await resendVerificationEmail();
    return { tone: "info", text: "Verification email sent. Check your inbox and spam folder." };
  });

  const checkVerified = () => run(async () => {
    const verified = await refreshEmailVerified();
    return verified ? null : { tone: "warn", text: "Not verified yet. Click the link in the email, then try again." };
  });

  return (
    <div className="flex flex-col items-center gap-3">
      <div>
        <h2 className="text-xl font-bold" style={{ color: "var(--ink)", fontFamily: "var(--font-display), system-ui" }}>
          Verify your email to predict
        </h2>
        <p className="mt-1.5 text-sm max-w-xs" style={{ color: "var(--muted)" }}>
          Click the verification link sent to {user?.email ?? "your email address"}, then come back here.
          No email? Use Resend below.
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        <button onClick={checkVerified} disabled={busy} className="btn-primary text-sm px-6 py-2.5">
          I&apos;ve verified
        </button>
        <button onClick={resend} disabled={busy} className="btn-ghost text-sm px-6 py-2.5">
          Resend email
        </button>
      </div>
      {status && (
        <p role="status" className="text-xs max-w-xs"
          style={{ color: status.tone === "warn" ? "var(--orange)" : "var(--muted)" }}>
          {status.text}
        </p>
      )}
    </div>
  );
}
