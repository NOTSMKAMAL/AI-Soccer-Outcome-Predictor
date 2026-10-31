"use client";

import { useEffect, useId, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { describeAuthError } from "@/lib/authErrors";
import { requestPasswordReset } from "@/lib/passwordReset";

// ── Icons ─────────────────────────────────────────────────────────────────────

function SoccerBall() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
      <path d="M2 12h20"/>
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
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5" style={{ minWidth: 0 }}>
      <label htmlFor={id} className="text-xs font-medium" style={{ color: "var(--muted)" }}>
        {label}
      </label>
      <div
        className="input-box flex items-center gap-2.5 rounded-[10px] px-3 transition-all duration-200"
        style={{
          minWidth: 0,
          background: "var(--surface-2)",
          border: `1px solid ${error ? "var(--danger-edge)" : "var(--border-s)"}`,
        }}
      >
        <span style={{ color: "var(--muted-2)", display: "inline-flex", flexShrink: 0 }}>
          <IconC />
        </span>
        <input
          id={id}
          type={type}
          aria-invalid={error ? true : undefined}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          autoComplete={autoComplete}
          style={{
            flex: 1,
            minWidth: 0,
            padding: "12px 0",
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
      {error && <p className="text-xs" style={{ color: "var(--danger)" }}>{error}</p>}
    </div>
  );
}

// ── Auth page ─────────────────────────────────────────────────────────────────

export default function AuthPage() {
  const { user, loading, accountDeleted, signIn, signUp, signInWithGoogle, resetPassword } = useAuth();
  const router = useRouter();

  const [tab, setTab] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [globalError, setGlobalError] = useState("");
  const [notice, setNotice] = useState("");

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
      setGlobalError(describeAuthError(err));
    } finally {
      setBusy(false);
    }
  };

  const handleForgotPassword = async () => {
    setGlobalError("");
    setNotice("");
    if (!email.includes("@")) {
      setErrors({ email: "Enter your email above, then press Forgot? again." });
      return;
    }
    setErrors({});
    setBusy(true);
    const { sent, message } = await requestPasswordReset(email, resetPassword);
    setBusy(false);
    if (sent) setNotice(message);
    else setGlobalError(message);
  };

  const handleGoogle = async () => {
    setBusy(true);
    setGlobalError("");
    try {
      await signInWithGoogle();
      router.replace("/dashboard");
    } catch (err: unknown) {
      setGlobalError(describeAuthError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      style={{ minHeight: "100dvh", gridTemplateColumns: "1.05fr 1fr", position: "relative" }}
      className="flex flex-col lg:grid"
    >
      {/* ── LEFT PANEL ── */}
      <aside
        style={{
          backgroundImage: "var(--depth)",
          borderRight: "1px solid var(--border-s)",
          position: "relative",
          overflow: "hidden",
          padding: "56px",
          color: "var(--ink)",
        }}
        className="hidden lg:flex lg:flex-col"
      >
        {/* Content */}
        <div style={{ position: "relative", zIndex: 1, display: "flex", flexDirection: "column", height: "100%", maxWidth: 520, margin: "0 auto", width: "100%" }}>
          {/* Brand */}
          <Link href="/" replace className="flex items-center gap-3 mb-14">
            <span style={{ fontWeight: 700, fontSize: 15, letterSpacing: "-0.01em", fontFamily: "var(--font-display), system-ui" }}>
              FUTURE FC
            </span>
          </Link>

          {/* Title */}
          <p
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
          </p>
          <p style={{ fontSize: 16, lineHeight: 1.55, color: "var(--ink-2)", marginBottom: 36 }}>
            Create an account to access live fixtures, AI predictions and match insights across
            the top leagues.
          </p>

          {/* Steps */}
          <ol style={{ listStyle: "none", padding: 0, margin: "0 0 auto", display: "flex", flexDirection: "column", gap: 10 }}>
            {[
              { n: "01", title: "Create your account", desc: "Email / password or Google — Firebase handles auth." },
              { n: "02", title: "Browse fixtures", desc: "Real football-data.org data across six top competitions." },
              { n: "03", title: "Generate predictions", desc: "One-click probabilities with Gemini reasoning and confidence." },
            ].map((s) => (
              <li
                key={s.n}
                style={{
                  display: "flex", alignItems: "flex-start", gap: 14,
                  padding: "14px 18px",
                  background: "var(--surface-2)",
                  borderRadius: 14,
                  boxShadow: "inset 0 0 0 1px var(--border-s)",
                }}
              >
                <span
                  style={{
                    fontFamily: "var(--font-display), monospace", fontSize: 11, fontWeight: 700, letterSpacing: "0.06em",
                    color: "var(--primary-text)",
                    background: "var(--primary-soft)",
                    padding: "5px 9px",
                    borderRadius: 8,
                    boxShadow: "inset 0 0 0 1px var(--primary-edge)",
                    flexShrink: 0,
                  }}
                >
                  {s.n}
                </span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)" }}>{s.title}</div>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 3, lineHeight: 1.5 }}>{s.desc}</div>
                </div>
              </li>
            ))}
          </ol>

          {/* Footer disclaimer */}
          <div style={{ marginTop: 32, display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: "var(--muted)" }}>
            <InfoIcon />
            <span>Analytics and entertainment only. Not betting advice.</span>
          </div>
        </div>
      </aside>

      {/* ── RIGHT PANEL ── */}
      <main
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr)",
          placeItems: "center",
          padding: "max(48px, env(safe-area-inset-top, 0px)) clamp(16px, 4vw, 32px) 48px",
          background: "var(--bg)",
        }}
      >
        {/* Mobile brand */}
        <div className="hidden max-lg:flex mb-6 items-center gap-2.5">
          <span style={{ fontWeight: 700, fontSize: 15, color: "var(--ink)", fontFamily: "var(--font-display), system-ui" }}>
            FUTURE FC
          </span>
        </div>

        <div
          style={{
            width: "100%", maxWidth: 440,
            background: "var(--surface)",
            borderRadius: 20,
            boxShadow: "inset 0 0 0 1px var(--border-s)",
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
                background: "var(--primary)",
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
                aria-pressed={tab === t}
                style={{
                  position: "relative", zIndex: 1,
                  padding: "10px",
                  fontSize: 13,
                  fontWeight: 600,
                  color: tab === t ? "var(--on-accent)" : "var(--muted)",
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
            <h1 style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.025em", margin: "0 0 5px", color: "var(--ink)" }}>
              {tab === "signin" ? "Welcome back" : "Create your account"}
            </h1>
            <p style={{ fontSize: 13, color: "var(--muted)", margin: 0 }}>
              {tab === "signin" ? "Sign in to view today's prediction board." : "Free to use. No payment needed."}
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
            className={busy ? undefined : "hover-fill-strong"}
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
                    disabled={busy}
                    style={{ minHeight: 24, fontSize: 12, color: "var(--primary-text)", background: "none", border: "none", cursor: "pointer", flexShrink: 0 }}
                    onClick={handleForgotPassword}
                  >
                    Forgot?
                  </button>
                ) : undefined
              }
            />

            {(notice || accountDeleted) && (
              <div
                role="status"
                style={{
                  padding: "10px 14px",
                  borderRadius: 10,
                  background: "var(--primary-soft)",
                  border: "1px solid var(--primary-edge)",
                }}
              >
                <p style={{ margin: 0, fontSize: 13, color: "var(--ink-2)" }}>
                  {notice || "Your account has been deleted."}
                </p>
              </div>
            )}

            {globalError && (
              <div
                style={{
                  padding: "10px 14px",
                  borderRadius: 10,
                  background: "var(--danger-soft)",
                  border: "1px solid var(--danger-edge)",
                }}
              >
                <p style={{ margin: 0, fontSize: 13, color: "var(--danger)" }}>{globalError}</p>
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

          {/* Shown on both tabs: Continue with Google can also create an account */}
          <p style={{ marginTop: 16, textAlign: "center", fontSize: 12, color: "var(--muted)", lineHeight: 1.5 }}>
            By creating an account you agree to the{" "}
            <Link href="/terms" style={{ color: "var(--primary-text)" }}>Terms</Link> and{" "}
            <Link href="/privacy" style={{ color: "var(--primary-text)" }}>Privacy Policy</Link>.
          </p>

          {/* Switch */}
          <p style={{ marginTop: 12, textAlign: "center", fontSize: 13, color: "var(--muted)" }}>
            {tab === "signin" ? (
              <>
                Need an account?{" "}
                <button
                  type="button"
                  onClick={() => { setTab("signup"); setErrors({}); setGlobalError(""); }}
                  style={{ minHeight: 24, color: "var(--primary-text)", background: "none", border: "none", cursor: "pointer", fontWeight: 600 }}
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
                  style={{ minHeight: 24, color: "var(--primary-text)", background: "none", border: "none", cursor: "pointer", fontWeight: 600 }}
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
