"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

type Stage = "idle" | "confirm" | "reauth";

const WRONG_PASSWORD_CODES = ["auth/wrong-password", "auth/invalid-credential", "auth/invalid-login-credentials"];
const POPUP_CLOSED_CODES = ["auth/popup-closed-by-user", "auth/cancelled-popup-request"];

const dangerButton: React.CSSProperties = {
  padding: "9px 14px", borderRadius: 10, fontSize: 13, fontWeight: 600, cursor: "pointer",
  background: "var(--danger-soft)", color: "var(--danger)",
  border: "1px solid var(--danger-edge)",
};
const plainButton: React.CSSProperties = {
  padding: "9px 14px", borderRadius: 10, fontSize: 13, fontWeight: 500, cursor: "pointer",
  background: "var(--surface-2)", color: "var(--ink-2)",
  border: "1px solid var(--border-strong)",
};

function describeError(err: unknown): string {
  const code = (err as { code?: string })?.code ?? "";
  if (WRONG_PASSWORD_CODES.includes(code)) return "That password isn't right. Please try again.";
  if (POPUP_CLOSED_CODES.includes(code)) return "Sign-in was cancelled, so nothing was deleted.";
  if (code === "auth/too-many-requests") return "Too many attempts. Please wait a few minutes and try again.";
  const message = err instanceof Error ? err.message : "";
  return message.replace(/^API \d+:\s*/, "") || "Something went wrong, so nothing was deleted. Please try again.";
}

/** Account settings section: confirm, sign in again if needed, delete. */
export default function DeleteAccountSection() {
  const { deleteAccount, hasPasswordSignIn, reauthenticate } = useAuth();
  const router = useRouter();
  const [stage, setStage] = useState<Stage>("idle");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const usesPassword = hasPasswordSignIn();

  const attemptDelete = async () => {
    await deleteAccount();
    router.replace("/auth");
  };

  const handleConfirm = async () => {
    setBusy(true);
    setError("");
    try {
      await attemptDelete();
    } catch (err: unknown) {
      if (err instanceof Error && err.message.startsWith("API 428:")) setStage("reauth");
      else setError(describeError(err));
    } finally {
      setBusy(false);
    }
  };

  const handleReauth = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await reauthenticate(usesPassword ? password : undefined);
      await attemptDelete();
    } catch (err: unknown) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  };

  const cancel = () => {
    setStage("idle");
    setPassword("");
    setError("");
  };

  return (
    <div style={{ marginTop: 20, paddingTop: 18, borderTop: "1px solid var(--border)" }}>
      <h3 style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)", margin: "0 0 4px" }}>Delete account</h3>

      {stage === "idle" && (
        <>
          <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 10px" }}>
            Permanently removes your account and your daily prediction counts.
          </p>
          <button type="button" onClick={() => setStage("confirm")} style={dangerButton}>
            Delete account
          </button>
        </>
      )}

      {stage === "confirm" && (
        <>
          <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 10px" }}>
            This can&apos;t be undone. You&apos;ll be signed out and your account will be gone.
          </p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" onClick={cancel} disabled={busy} style={plainButton}>Keep my account</button>
            <button type="button" onClick={handleConfirm} disabled={busy} style={dangerButton}>
              {busy ? "Deleting…" : "Yes, delete my account"}
            </button>
          </div>
        </>
      )}

      {stage === "reauth" && (
        <form onSubmit={handleReauth}>
          <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 10px" }}>
            For your security, please sign in again to confirm it&apos;s you.
            Your account will be deleted straight after.
          </p>
          {usesPassword && (
            <input
              type="password"
              aria-label="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Your password"
              autoComplete="current-password"
              style={{
                width: "100%", boxSizing: "border-box", marginBottom: 10,
                padding: "9px 12px", borderRadius: 10, fontSize: 14,
                background: "var(--surface-2)", color: "var(--ink)",
                border: "1px solid var(--border-strong)", outline: "none",
              }}
            />
          )}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" onClick={cancel} disabled={busy} style={plainButton}>Keep my account</button>
            <button type="submit" disabled={busy || (usesPassword && !password)} style={dangerButton}>
              {busy ? "Deleting…" : usesPassword ? "Confirm and delete" : "Continue with Google and delete"}
            </button>
          </div>
        </form>
      )}

      {error && <p role="alert" style={{ margin: "10px 0 0", fontSize: 12, color: "var(--danger)" }}>{error}</p>}
    </div>
  );
}
