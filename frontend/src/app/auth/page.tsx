"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

// ── Icons ─────────────────────────────────────────────────────────────────────

function SparkleLg() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2 14 9l7 2-7 2-2 7-2-7-7-2 7-2 2-7Z" />
    </svg>
  );
}
function MailIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" />
    </svg>
  );
}
function LockIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="11" width="16" height="10" rx="2" /><path d="M8 11V8a4 4 0 1 1 8 0v3" />
    </svg>
  );
}
function UserIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21a8 8 0 0 0-16 0" /><circle cx="12" cy="7" r="4" />
    </svg>
  );
}
function GoogleG() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M21.6 12.2c0-.7-.1-1.4-.2-2H12v3.9h5.4a4.6 4.6 0 0 1-2 3v2.5h3.2c1.9-1.8 3-4.4 3-7.4Z" fill="#4285F4"/>
      <path d="M12 22c2.7 0 5-.9 6.6-2.4l-3.2-2.5c-.9.6-2 1-3.4 1a5.9 5.9 0 0 1-5.6-4.1H3.1v2.6A10 10 0 0 0 12 22Z" fill="#34A853"/>
      <path d="M6.4 14a6 6 0 0 1 0-3.8V7.5H3.1a10 10 0 0 0 0 9l3.3-2.6Z" fill="#FBBC05"/>
      <path d="M12 6.1c1.5 0 2.8.5 3.9 1.5l2.9-2.8A10 10 0 0 0 3.1 7.5l3.3 2.6A5.9 5.9 0 0 1 12 6.1Z" fill="#EA4335"/>
    </svg>
  );
}
function SpinnerSvg() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" style={{ animation: "orbSpin 0.8s linear infinite" }}>
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="2.5" strokeOpacity="0.25"/>
      <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
    </svg>
  );
}
function InfoIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>
    </svg>
  );
}

// ── Field component ───────────────────────────────────────────────────────────

function Field({
  label,
  type = "text",
  Icon: IconC,
  value,
  onChange,
  placeholder,
  error,
  autoComplete,
  extra,
}: {
  label: string;
  type?: string;
  Icon: () => JSX.Element;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder: string;
  error?: string;
  autoComplete?: string;
  extra?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5" style={{ minWidth: 0 }}>
      <label className="text-xs font-medium" style={{ color: "var(--muted)" }}>
        {label}
      </label>
      <div
        className="flex items-center gap-2.5 rounded-[10px] px-3 py-2.5 transition-all duration-200"
        style={{
          minWidth: 0,
          background: "var(--surface-2)",
          border: `1px solid ${error ? "rgba(248,113,113,0.5)" : "var(--border-s)"}`,
          boxShadow: error ? "0 0 0 3px rgba(248,113,113,0.12)" : undefined,
        }}
      >
        <span style={{ color: "var(--muted-2)", display: "inline-flex", flexShrink: 0 }}>
          <IconC />
        </span>
        <input
          type={type}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          autoComplete={autoComplete}
          style={{
            flex: 1,
            background: "transparent",
            border: "none",
            outline: "none",
            color: "var(--ink)",
            fontSize: "14px",
          }}
          className="placeholder:text-[--muted-2]"
        />
        {extra}
      </div>
      {error && <p className="text-xs" style={{ color: "var(--lo)" }}>{error}</p>}
    </div>
  );
}

// ── Auth page ─────────────────────────────────────────────────────────────────

export default function AuthPage() {
  const { user, loading, signIn, signUp, signInWithGoogle } = useAuth();
  const router = useRouter();

  const [tab, setTab] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [globalError, setGlobalError] = useState("");

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [user, loading, router]);

  if (loading || user) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!email.includes("@")) errs.email = "Enter a valid email.";
    if (password.length < 6) errs.password = "At least 6 characters.";
    if (tab === "signup" && !firstName) errs.firstName = "Required";
    setErrors(errs);
    if (Object.keys(errs).length) return;

    setBusy(true);
    setGlobalError("");
    try {
      if (tab === "signup") {
        const displayName = [firstName, lastName].filter(Boolean).join(" ");
        await signUp(email, password, displayName || undefined);
      } else {
        await signIn(email, password);
      }
      router.replace("/dashboard");
    } catch (err: unknown) {
      setGlobalError(err instanceof Error ? err.message : "Authentication failed.");
    } finally {
      setBusy(false);
    }
  };

  const handleGoogle = async () => {
    setBusy(true);
    setGlobalError("");
    try {
      await signInWithGoogle();
      router.replace("/dashboard");
    } catch (err: unknown) {
      setGlobalError(err instanceof Error ? err.message : "Google sign-in failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      style={{ minHeight: "100vh", display: "grid", gridTemplateColumns: "1.05fr 1fr", position: "relative" }}
      className="max-lg:flex max-lg:flex-col"
    >
      {/* ── LEFT PANEL ── */}
      <aside
        style={{
          background: "linear-gradient(135deg, #07061B 0%, #1A0B40 40%, #4C1D95 100%)",
          position: "relative",
          overflow: "hidden",
          padding: "56px",
          display: "flex",
          flexDirection: "column",
          color: "white",
        }}
        className="max-lg:hidden"
      >
        {/* Animated orbs */}
        <div aria-hidden style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none" }}>
          <div
            style={{
              position: "absolute", borderRadius: "50%",
              width: 460, height: 460, top: -160, right: -120,
              background: "radial-gradient(closest-side, rgba(167,139,250,0.55), transparent 70%)",
              filter: "blur(60px)",
              animation: "drift 18s ease infinite",
            }}
          />
          <div
            style={{
              position: "absolute", borderRadius: "50%",
              width: 380, height: 380, bottom: -100, left: -100,
              background: "radial-gradient(closest-side, rgba(236,72,153,0.4), transparent 70%)",
              filter: "blur(60px)",
              animation: "drift 18s ease -7s infinite",
            }}
          />
        </div>

        <style>{`@keyframes drift { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-16px)} }`}</style>

        {/* Content */}
        <div style={{ position: "relative", zIndex: 1, display: "flex", flexDirection: "column", height: "100%", maxWidth: 520, margin: "0 auto", width: "100%" }}>
          {/* Brand */}
          <Link href="/" className="flex items-center gap-3 mb-14">
            <div
              style={{
                width: 32, height: 32, borderRadius: 10,
                background: "linear-gradient(135deg, rgba(255,255,255,0.3), rgba(255,255,255,0.1))",
                display: "grid", placeItems: "center",
                boxShadow: "inset 0 1px 0 rgba(255,255,255,0.3)",
              }}
            >
              <SparkleLg />
            </div>
            <span style={{ fontWeight: 600, fontSize: 15, letterSpacing: "-0.01em" }}>
              AI Sports Predictor
            </span>
          </Link>

          {/* Title */}
          <h1
            style={{
              fontSize: "clamp(28px, 3vw, 42px)",
              lineHeight: 1.08,
              letterSpacing: "-0.03em",
              fontWeight: 700,
              marginBottom: 14,
              textWrap: "balance",
            }}
          >
            Get started with AI match predictions.
          </h1>
          <p style={{ fontSize: 16, lineHeight: 1.55, color: "rgba(255,255,255,0.72)", marginBottom: 36 }}>
            Create an account to access live fixtures, AI predictions and match insights across
            the top leagues.
          </p>

          {/* Steps */}
          <ol style={{ listStyle: "none", padding: 0, margin: "0 0 auto", display: "flex", flexDirection: "column", gap: 10 }}>
            {[
              { n: "01", title: "Create your account", desc: "Email / password or Google — Firebase handles auth." },
              { n: "02", title: "Browse live fixtures", desc: "Real SportMonks data across MLS, PL, LaLiga and more." },
              { n: "03", title: "Generate predictions", desc: "One-click Gemini reasoning with confidence and risk factors." },
            ].map((s) => (
              <li
                key={s.n}
                style={{
                  display: "flex", alignItems: "flex-start", gap: 14,
                  padding: "14px 18px",
                  background: "rgba(255,255,255,0.06)",
                  borderRadius: 14,
                  boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.12)",
                  backdropFilter: "blur(8px)",
                }}
              >
                <span
                  style={{
                    fontFamily: "monospace", fontSize: 11, fontWeight: 700, letterSpacing: "0.06em",
                    color: "white",
                    background: "rgba(255,255,255,0.14)",
                    padding: "5px 9px",
                    borderRadius: 8,
                    boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.18)",
                    flexShrink: 0,
                  }}
                >
                  {s.n}
                </span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "white" }}>{s.title}</div>
                  <div style={{ fontSize: 12, color: "rgba(255,255,255,0.65)", marginTop: 3, lineHeight: 1.5 }}>{s.desc}</div>
                </div>
              </li>
            ))}
          </ol>

          {/* Footer disclaimer */}
          <div style={{ marginTop: 32, display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: "rgba(255,255,255,0.5)" }}>
            <InfoIcon />
            <span>Analytics and entertainment only. Not betting advice.</span>
          </div>
        </div>
      </aside>

      {/* ── RIGHT PANEL ── */}
      <main
        style={{
          display: "grid",
          placeItems: "center",
          padding: "48px 32px",
          background: "var(--bg)",
        }}
      >
        {/* Mobile brand */}
        <div className="hidden max-lg:flex mb-6 items-center gap-2.5">
          <div
            style={{
              width: 28, height: 28, borderRadius: 8,
              background: "linear-gradient(135deg, #A78BFA, #7C3AED)",
              display: "grid", placeItems: "center", color: "white",
            }}
          >
            <SparkleLg />
          </div>
          <span style={{ fontWeight: 600, fontSize: 15, color: "var(--ink)" }}>
            AI Sports Predictor
          </span>
        </div>

        <div
          style={{
            width: "100%", maxWidth: 440,
            background: "var(--surface)",
            borderRadius: 20,
            boxShadow: "0 30px 70px -30px rgba(0,0,0,0.5), inset 0 0 0 1px var(--border-s)",
            padding: 32,
          }}
        >
          {/* Tab toggle */}
          <div
            style={{
              position: "relative",
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              background: "var(--surface-2)",
              borderRadius: 999,
              padding: 4,
              marginBottom: 28,
              boxShadow: "inset 0 0 0 1px var(--border)",
            }}
          >
            {/* Sliding indicator */}
            <div
              style={{
                position: "absolute",
                top: 4, bottom: 4,
                left: 4,
                width: "calc(50% - 4px)",
                borderRadius: 999,
                background: "linear-gradient(180deg, #9C70F8, #7C3AED)",
                boxShadow: "0 6px 16px -4px rgba(124,58,237,0.6)",
                transition: "transform 0.3s cubic-bezier(0.2,0.6,0.2,1)",
                transform: tab === "signup" ? "translateX(100%)" : "translateX(0)",
                zIndex: 0,
              }}
            />
            {(["signin", "signup"] as const).map((t) => (
              <button
                key={t}
                onClick={() => { setTab(t); setErrors({}); setGlobalError(""); }}
                type="button"
                style={{
                  position: "relative", zIndex: 1,
                  padding: "10px",
                  fontSize: 13,
                  fontWeight: 600,
                  color: tab === t ? "white" : "var(--muted)",
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  borderRadius: 999,
                  transition: "color 0.2s",
                }}
              >
                {t === "signin" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>

          {/* Header */}
          <div style={{ marginBottom: 22 }}>
            <h2 style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.025em", margin: "0 0 5px", color: "var(--ink)" }}>
              {tab === "signin" ? "Welcome back" : "Create your account"}
            </h2>
            <p style={{ fontSize: 13, color: "var(--muted)", margin: 0 }}>
              {tab === "signin" ? "Sign in to view today's prediction board." : "Free to start. Cancel anytime."}
            </p>
          </div>

          {/* Google */}
          <button
            type="button"
            onClick={handleGoogle}
            disabled={busy}
            style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              gap: 10, width: "100%",
              padding: "11px 16px",
              background: "var(--surface-2)",
              color: "var(--ink)",
              border: "1px solid var(--border-s)",
              borderRadius: 10,
              fontSize: 14, fontWeight: 500,
              cursor: busy ? "not-allowed" : "pointer",
              transition: "background 0.2s",
              marginBottom: 20,
              opacity: busy ? 0.5 : 1,
            }}
            onMouseEnter={(e) => !busy && ((e.currentTarget as HTMLButtonElement).style.background = "var(--surface-3)")}
            onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "var(--surface-2)")}
          >
            <GoogleG />
            <span>{tab === "signin" ? "Continue with Google" : "Sign up with Google"}</span>
          </button>

          {/* Divider */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
            <div style={{ flex: 1, height: 1, background: "var(--border-s)" }} />
            <span style={{ fontSize: 12, color: "var(--muted-2)" }}>
              or {tab === "signin" ? "sign in" : "sign up"} with email
            </span>
            <div style={{ flex: 1, height: 1, background: "var(--border-s)" }} />
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }} noValidate>
            {tab === "signup" && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, minWidth: 0 }}>
                <div style={{ minWidth: 0 }}>
                  <Field
                    label="First name"
                    Icon={UserIcon}
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    placeholder="Alex"
                    error={errors.firstName}
                    autoComplete="given-name"
                  />
                </div>
                <div style={{ minWidth: 0 }}>
                  <Field
                    label="Last name"
                    Icon={UserIcon}
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    placeholder="Morgan"
                    autoComplete="family-name"
                  />
                </div>
              </div>
            )}

            <Field
              label="Email"
              type="email"
              Icon={MailIcon}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              error={errors.email}
              autoComplete="email"
            />

            <Field
              label="Password"
              type="password"
              Icon={LockIcon}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={tab === "signin" ? "Your password" : "At least 6 characters"}
              error={errors.password}
              autoComplete={tab === "signin" ? "current-password" : "new-password"}
              extra={
                tab === "signin" ? (
                  <button
                    type="button"
                    style={{ fontSize: 12, color: "var(--accent-2)", background: "none", border: "none", cursor: "pointer", flexShrink: 0 }}
                    onClick={(e) => e.preventDefault()}
                  >
                    Forgot?
                  </button>
                ) : undefined
              }
            />

            {globalError && (
              <div
                style={{
                  padding: "10px 14px",
                  borderRadius: 10,
                  background: "var(--lo-bg)",
                  border: "1px solid rgba(248,113,113,0.25)",
                }}
              >
                <p style={{ margin: 0, fontSize: 13, color: "var(--lo)" }}>{globalError}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="btn-primary"
              style={{ width: "100%", padding: "16px 22px", fontSize: 15, marginTop: 4, borderRadius: 12 }}
            >
              {busy ? (
                <>
                  <SpinnerSvg />
                  {tab === "signin" ? "Signing in…" : "Creating account…"}
                </>
              ) : (
                tab === "signin" ? "Sign in" : "Create account"
              )}
            </button>
          </form>

          {/* Switch */}
          <p style={{ marginTop: 20, textAlign: "center", fontSize: 13, color: "var(--muted)" }}>
            {tab === "signin" ? (
              <>
                Need an account?{" "}
                <button
                  type="button"
                  onClick={() => { setTab("signup"); setErrors({}); setGlobalError(""); }}
                  style={{ color: "var(--accent-2)", background: "none", border: "none", cursor: "pointer", fontWeight: 600 }}
                >
                  Sign up
                </button>
              </>
            ) : (
              <>
                Already have an account?{" "}
                <button
                  type="button"
                  onClick={() => { setTab("signin"); setErrors({}); setGlobalError(""); }}
                  style={{ color: "var(--accent-2)", background: "none", border: "none", cursor: "pointer", fontWeight: 600 }}
                >
                  Log in
                </button>
              </>
            )}
          </p>
        </div>
      </main>
    </div>
  );
}
