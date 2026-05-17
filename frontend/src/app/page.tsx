"use client";
import Link from "next/link";

// ── Static hero preview card ──────────────────────────────────────────────────

const SAMPLE_FIXTURES = [
  { league: "EPL", leagueColor: "#A78BFA", home: "Liverpool", away: "Man City",  status: "live", minute: "67'", conf: 72, level: "medium" },
  { league: "LIG", leagueColor: "#EE8707", home: "Real Ma…", away: "Barcel…",   status: "today", time: "21:00", conf: 68, level: "medium" },
  { league: "SA",  leagueColor: "#4A9FFF", home: "Inter Mil…", away: "AC Mil…", status: "today", time: "20:45", conf: 81, level: "high" },
];

function ConfDot({ level }: { level: string }) {
  const color = level === "high" ? "#34D399" : level === "medium" ? "#FACC15" : "#F87171";
  return <span style={{ width: 6, height: 6, borderRadius: "50%", background: color, display: "inline-block", marginRight: 4 }} />;
}

function HeroPreviewCard() {
  return (
    <div style={{ position: "relative", flex: "0 0 auto", width: "min(460px, 100%)" }}>
      {/* Glow */}
      <div aria-hidden style={{
        position: "absolute", inset: "-40px -60px",
        background: "radial-gradient(ellipse 70% 60% at 55% 45%, rgba(124,58,237,0.35) 0%, transparent 70%)",
        pointerEvents: "none",
      }} />
      {/* Card */}
      <div style={{
        position: "relative",
        background: "var(--surface)",
        borderRadius: 20,
        boxShadow: "0 30px 70px -24px rgba(0,0,0,0.7), inset 0 0 0 1px rgba(255,255,255,0.10)",
        overflow: "hidden",
      }}>
        {/* Top accent line */}
        <div style={{ height: 2, background: "linear-gradient(90deg, transparent, #A78BFA 30%, #7C3AED 70%, transparent)" }} />

        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 20px 12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#34D399", display: "inline-block", boxShadow: "0 0 6px #34D399" }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)" }}>Today&apos;s prediction board</span>
          </div>
          <span style={{
            fontSize: 11, color: "var(--muted)", fontWeight: 500,
            padding: "3px 8px", borderRadius: 6,
            background: "var(--surface-2)",
            border: "1px solid var(--border)",
          }}>
            SportMonks live
          </span>
        </div>

        {/* Fixture rows */}
        <div style={{ padding: "0 12px" }}>
          {SAMPLE_FIXTURES.map((f, i) => (
            <div key={i} style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "10px 8px",
              borderRadius: 10,
              borderTop: i > 0 ? "1px solid var(--border)" : "none",
            }}>
              {/* League badge */}
              <span style={{
                fontSize: 10, fontWeight: 700, letterSpacing: "0.05em",
                color: f.leagueColor, minWidth: 28, flexShrink: 0,
              }}>
                {f.league}
              </span>

              {/* Teams */}
              <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 5, fontSize: 12, fontWeight: 500, color: "var(--ink-2)", minWidth: 0 }}>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.home}</span>
                <span style={{ color: "var(--muted-2)", flexShrink: 0 }}>vs</span>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.away}</span>
              </div>

              {/* Status */}
              <span style={{ fontSize: 11, color: "var(--muted)", whiteSpace: "nowrap", flexShrink: 0 }}>
                {f.status === "live" ? (
                  <><span style={{ color: "#F87171" }}>● </span>Live · {f.minute}</>
                ) : (
                  <>Today · {f.time}</>
                )}
              </span>

              {/* Confidence chip */}
              <span style={{
                fontSize: 11, fontWeight: 700,
                padding: "3px 8px", borderRadius: 20,
                background: f.level === "high" ? "rgba(52,211,153,0.12)" : "rgba(250,204,21,0.12)",
                color: f.level === "high" ? "#34D399" : "#FACC15",
                display: "flex", alignItems: "center", flexShrink: 0,
              }}>
                <ConfDot level={f.level} />
                {f.conf}%
              </span>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "12px 20px 16px",
          borderTop: "1px solid var(--border)",
          marginTop: 4,
        }}>
          <span style={{ fontSize: 12, color: "var(--muted)" }}>3 of 14 fixtures · 5 leagues</span>
          <Link href="/auth" style={{ fontSize: 12, color: "var(--accent-2)", fontWeight: 600, textDecoration: "none" }}>
            View all →
          </Link>
        </div>
      </div>
    </div>
  );
}

// ── Data ──────────────────────────────────────────────────────────────────────

const LEAGUES = [
  { name: "Premier League", country: "England", color: "#9381FF" },
  { name: "La Liga",         country: "Spain",   color: "#EE8707" },
  { name: "Serie A",         country: "Italy",   color: "#4A9FFF" },
  { name: "Bundesliga",      country: "Germany", color: "#D4021D" },
  { name: "Ligue 1",         country: "France",  color: "#4A9FFF" },
];

const FEATURES = [
  {
    icon: <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />,
    title: "Real match data",
    desc: "Live SportMonks fixtures, lineups and stats. No guessing, no scraped tables.",
    meta: "SportMonks v3",
  },
  {
    icon: <path d="M13 10V3L4 14h7v7l9-11h-7z" />,
    title: "AI-powered predictions",
    desc: "Gemini synthesises form, head-to-head, venue and squad context into a single structured call.",
    meta: "Gemini 2.5 Flash",
  },
  {
    icon: <path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />,
    title: "Confidence and reasoning",
    desc: "Every verdict comes banded high / medium / low with a structured explanation of the key factors.",
    meta: "Transparent AI",
  },
  {
    icon: <path d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />,
    title: "League-focused dashboard",
    desc: "Premier League, La Liga, Serie A, Bundesliga, Ligue 1 — live fixtures across all five, every day.",
    meta: "5 top leagues",
  },
];

const STEPS = [
  { n: "01", title: "Sign in",                   desc: "Email / password or Google. Firebase Auth handles the rest." },
  { n: "02", title: "Browse today's matches",    desc: "Real fixtures across all five leagues, filtered by date and league." },
  { n: "03", title: "Generate an AI prediction", desc: "One click sends the fixture context to Gemini for a structured verdict." },
  { n: "04", title: "Review the breakdown",      desc: "Confidence band, reasoning, weighted factors and risk — every input on display." },
];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function HomePage() {
  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)" }}>

      {/* ── Ambient top glow ── */}
      <div aria-hidden style={{
        position: "fixed", inset: "0 0 auto 0", height: 600, pointerEvents: "none", zIndex: 0,
        background: "radial-gradient(ellipse 70% 50% at 50% 0%, rgba(124,58,237,0.18) 0%, transparent 70%)",
      }} />

      {/* ── Landing nav ── */}
      <header style={{
        position: "sticky", top: 0, zIndex: 40,
        background: "color-mix(in srgb, var(--bg) 80%, transparent)",
        backdropFilter: "saturate(180%) blur(20px)",
        WebkitBackdropFilter: "saturate(180%) blur(20px)",
        borderBottom: "1px solid var(--border)",
      }}>
        <div style={{
          maxWidth: 1200, margin: "0 auto",
          padding: "14px 32px",
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 24,
        }}>
          {/* Brand */}
          <a href="#" style={{ display: "flex", alignItems: "center", gap: 10, fontWeight: 600, fontSize: 15, color: "var(--ink)", textDecoration: "none", letterSpacing: "-0.01em" }}>
            <div style={{
              width: 28, height: 28, borderRadius: 8,
              background: "linear-gradient(135deg, #A78BFA 0%, #7C3AED 100%)",
              display: "grid", placeItems: "center", color: "white",
              boxShadow: "0 6px 16px -4px rgba(124,58,237,0.6), inset 0 1px 0 rgba(255,255,255,0.3)",
            }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2 14 9l7 2-7 2-2 7-2-7-7-2 7-2 2-7Z" />
              </svg>
            </div>
            AI Sports<span style={{ color: "var(--accent-2)" }}> Predictor</span>
          </a>

          {/* Nav links */}
          <nav style={{ display: "flex", alignItems: "center", gap: 4 }} className="hidden sm:flex">
            {[
              { label: "Features",     href: "#features" },
              { label: "How it works", href: "#how-it-works" },
              { label: "Leagues",      href: "#leagues" },
            ].map(({ label, href }) => (
              <a key={href} href={href} style={{
                fontSize: 14, color: "var(--muted)", padding: "6px 14px",
                borderRadius: 8, textDecoration: "none",
                transition: "color 0.15s",
              }}
              onMouseEnter={e => (e.currentTarget.style.color = "var(--ink)")}
              onMouseLeave={e => (e.currentTarget.style.color = "var(--muted)")}
              >
                {label}
              </a>
            ))}
            <a href="/auth" style={{
              fontSize: 14, color: "var(--muted)", padding: "6px 14px",
              borderRadius: 8, textDecoration: "none",
              transition: "color 0.15s",
            }}
            onMouseEnter={e => (e.currentTarget.style.color = "var(--ink)")}
            onMouseLeave={e => (e.currentTarget.style.color = "var(--muted)")}
            >
              Sign in
            </a>
          </nav>

          {/* CTA */}
          <Link href="/auth" style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            padding: "9px 18px", borderRadius: 10, fontSize: 14, fontWeight: 600,
            background: "linear-gradient(135deg, #A78BFA 0%, #7C3AED 100%)",
            color: "white", textDecoration: "none",
            boxShadow: "0 6px 16px -4px rgba(124,58,237,0.5)",
            transition: "opacity 0.15s",
          }}>
            Get started
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </Link>
        </div>
      </header>

      {/* ── Hero ── */}
      <section style={{ position: "relative", zIndex: 1 }}>
        <div style={{
          maxWidth: 1200, margin: "0 auto", padding: "72px 32px 80px",
          display: "flex", alignItems: "center", gap: 64, flexWrap: "wrap",
        }}>
          {/* Left copy */}
          <div style={{ flex: "1 1 420px", minWidth: 0 }}>
            {/* Badge */}
            <div style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              padding: "5px 14px 5px 6px", borderRadius: 999,
              background: "rgba(139,92,246,0.12)",
              border: "1px solid rgba(139,92,246,0.28)",
              marginBottom: 28,
            }}>
              <span style={{
                width: 22, height: 22, borderRadius: "50%",
                background: "linear-gradient(135deg, #C4B5FD, #7C3AED)",
                display: "grid", placeItems: "center", color: "white", fontSize: 10,
              }}>
                <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2 14 9l7 2-7 2-2 7-2-7-7-2 7-2 2-7Z" />
                </svg>
              </span>
              <span style={{ fontSize: 12, fontWeight: 500, color: "var(--accent-2)" }}>
                Live football intelligence powered by AI
              </span>
            </div>

            <h1 style={{
              fontSize: "clamp(36px, 5vw, 58px)", lineHeight: 1.05,
              fontWeight: 700, letterSpacing: "-0.035em",
              color: "var(--ink)", margin: "0 0 20px",
            }}>
              Predict football outcomes with{" "}
              <em style={{
                fontStyle: "normal",
                background: "linear-gradient(135deg, #C4B5FD 0%, #A78BFA 30%, #7C3AED 70%, #6D28D9 100%)",
                WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent",
              }}>
                real match data
              </em>
              .
            </h1>

            <p style={{ fontSize: 18, lineHeight: 1.6, color: "var(--muted)", margin: "0 0 36px", maxWidth: 500 }}>
              AI Sports Predictor analyzes fixtures, team form, head-to-head history and match context to generate
              structured predictions for the top football leagues.
            </p>

            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 28 }}>
              <Link href="/auth" style={{
                display: "inline-flex", alignItems: "center", gap: 8,
                padding: "14px 28px", borderRadius: 12, fontSize: 16, fontWeight: 600,
                background: "linear-gradient(135deg, #A78BFA 0%, #7C3AED 100%)",
                color: "white", textDecoration: "none",
                boxShadow: "0 8px 24px -6px rgba(124,58,237,0.5)",
              }}>
                Get started
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </Link>
              <Link href="/dashboard" style={{
                display: "inline-flex", alignItems: "center", gap: 8,
                padding: "14px 28px", borderRadius: 12, fontSize: 16, fontWeight: 600,
                background: "var(--surface)", color: "var(--ink-2)", textDecoration: "none",
                border: "1px solid var(--border-strong)",
              }}>
                View live matches
              </Link>
            </div>

            {/* Trust row */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 20px" }}>
              {["No credit card", "Live SportMonks data", "Gemini reasoning"].map((t) => (
                <span key={t} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "var(--muted)" }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#34D399" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 6L9 17l-5-5" />
                  </svg>
                  {t}
                </span>
              ))}
            </div>
          </div>

          {/* Right preview card */}
          <HeroPreviewCard />
        </div>
      </section>

      {/* ── Leagues strip ── */}
      <section id="leagues" style={{ position: "relative", zIndex: 1, borderTop: "1px solid var(--border)", borderBottom: "1px solid var(--border)", background: "var(--surface)" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", padding: "20px 32px", display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap" }}>
          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--muted-2)", flexShrink: 0 }}>
            Covers the top five leagues
          </span>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {LEAGUES.map((l) => (
              <div key={l.name} style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "7px 14px", borderRadius: 999,
                background: "var(--surface-2)", border: "1px solid var(--border-strong)",
              }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: l.color, display: "inline-block" }} />
                <strong style={{ fontSize: 13, color: "var(--ink)", fontWeight: 600 }}>{l.name}</strong>
                <span style={{ fontSize: 12, color: "var(--muted)" }}>· {l.country}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section id="features" style={{ position: "relative", zIndex: 1, padding: "96px 32px" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <header style={{ textAlign: "center", marginBottom: 56 }}>
            <div style={{
              display: "inline-block", fontSize: 11, fontWeight: 700, letterSpacing: "0.12em",
              textTransform: "uppercase", color: "var(--accent-2)",
              marginBottom: 14,
            }}>
              Why this exists
            </div>
            <h2 style={{ fontSize: "clamp(28px, 4vw, 44px)", fontWeight: 700, letterSpacing: "-0.03em", color: "var(--ink)", margin: "0 0 16px" }}>
              Built for fans who want clarity, not noise.
            </h2>
            <p style={{ fontSize: 16, color: "var(--muted)", maxWidth: 560, margin: "0 auto", lineHeight: 1.6 }}>
              Four pillars run through every prediction — real-time data, AI reasoning, transparent confidence and a tight focus on the leagues that matter.
            </p>
          </header>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
            {FEATURES.map((f) => (
              <article key={f.title} style={{
                background: "var(--surface)", borderRadius: 20, padding: "28px 28px 24px",
                border: "1px solid var(--border)",
                transition: "transform 0.25s, box-shadow 0.25s",
                cursor: "default",
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLElement).style.transform = "translateY(-3px)";
                (e.currentTarget as HTMLElement).style.boxShadow = "0 20px 40px -16px rgba(0,0,0,0.4), inset 0 0 0 1px rgba(139,92,246,0.2)";
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLElement).style.transform = "";
                (e.currentTarget as HTMLElement).style.boxShadow = "";
              }}
              >
                <div style={{
                  width: 44, height: 44, borderRadius: 12, marginBottom: 20,
                  background: "rgba(139,92,246,0.12)", border: "1px solid rgba(139,92,246,0.22)",
                  display: "grid", placeItems: "center", color: "var(--accent-2)",
                }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    {f.icon}
                  </svg>
                </div>
                <h3 style={{ fontSize: 17, fontWeight: 600, letterSpacing: "-0.015em", color: "var(--ink)", margin: "0 0 8px" }}>{f.title}</h3>
                <p style={{ fontSize: 14, color: "var(--muted)", margin: "0 0 20px", lineHeight: 1.6 }}>{f.desc}</p>
                <div style={{ paddingTop: 16, borderTop: "1px solid var(--border)", fontSize: 11, color: "var(--muted-2)", fontFamily: "monospace" }}>
                  {f.meta}
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section id="how-it-works" style={{
        position: "relative", zIndex: 1, padding: "96px 32px",
        background: "var(--surface)",
        borderTop: "1px solid var(--border)", borderBottom: "1px solid var(--border)",
      }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <header style={{ textAlign: "center", marginBottom: 56 }}>
            <div style={{
              display: "inline-block", fontSize: 11, fontWeight: 700, letterSpacing: "0.12em",
              textTransform: "uppercase", color: "var(--accent-2)", marginBottom: 14,
            }}>
              How it works
            </div>
            <h2 style={{ fontSize: "clamp(28px, 4vw, 44px)", fontWeight: 700, letterSpacing: "-0.03em", color: "var(--ink)", margin: 0 }}>
              Four steps from sign-in to verdict.
            </h2>
          </header>

          <ol style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16, listStyle: "none", padding: 0, margin: 0 }}>
            {STEPS.map((s) => (
              <li key={s.n} style={{
                background: "var(--bg)", borderRadius: 20, padding: "28px",
                border: "1px solid var(--border)",
              }}>
                <div style={{
                  fontFamily: "monospace", fontSize: 12, fontWeight: 700, letterSpacing: "0.08em",
                  color: "var(--accent-2)", marginBottom: 14,
                  padding: "5px 10px", borderRadius: 8, display: "inline-block",
                  background: "rgba(139,92,246,0.10)", border: "1px solid rgba(139,92,246,0.20)",
                }}>
                  {s.n}
                </div>
                <h3 style={{ fontSize: 16, fontWeight: 600, letterSpacing: "-0.015em", color: "var(--ink)", margin: "0 0 8px" }}>{s.title}</h3>
                <p style={{ fontSize: 14, color: "var(--muted)", margin: 0, lineHeight: 1.6 }}>{s.desc}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ── CTA ── */}
      <section style={{ position: "relative", zIndex: 1, padding: "96px 32px" }}>
        <div style={{ maxWidth: 640, margin: "0 auto", textAlign: "center" }}>
          <h2 style={{ fontSize: "clamp(28px, 4vw, 42px)", fontWeight: 700, letterSpacing: "-0.03em", color: "var(--ink)", margin: "0 0 16px" }}>
            Ready to see today&apos;s board?
          </h2>
          <p style={{ fontSize: 16, color: "var(--muted)", maxWidth: 480, margin: "0 auto 32px", lineHeight: 1.6 }}>
            Sign in to access live fixtures and AI predictions across all five leagues.
          </p>
          <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
            <Link href="/auth" style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              padding: "14px 32px", borderRadius: 12, fontSize: 16, fontWeight: 600,
              background: "linear-gradient(135deg, #A78BFA 0%, #7C3AED 100%)",
              color: "white", textDecoration: "none",
              boxShadow: "0 8px 24px -6px rgba(124,58,237,0.5)",
            }}>
              Create your account
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </Link>
            <Link href="/auth" style={{
              display: "inline-flex", alignItems: "center",
              padding: "14px 28px", borderRadius: 12, fontSize: 16, fontWeight: 600,
              background: "var(--surface)", color: "var(--ink-2)", textDecoration: "none",
              border: "1px solid var(--border-strong)",
            }}>
              I already have one
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer style={{
        position: "relative", zIndex: 1,
        borderTop: "1px solid var(--border)",
        padding: "32px",
      }}>
        <div style={{
          maxWidth: 1200, margin: "0 auto",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          flexWrap: "wrap", gap: 16,
        }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, fontWeight: 600, fontSize: 14, color: "var(--ink)", marginBottom: 6 }}>
              <div style={{
                width: 24, height: 24, borderRadius: 7,
                background: "linear-gradient(135deg, #A78BFA, #7C3AED)",
                display: "grid", placeItems: "center", color: "white",
              }}>
                <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2 14 9l7 2-7 2-2 7-2-7-7-2 7-2 2-7Z" />
                </svg>
              </div>
              AI Sports Predictor
            </div>
            <p style={{ fontSize: 12, color: "var(--muted-2)", margin: 0 }}>
              SportMonks data · Gemini reasoning · Firebase Auth
            </p>
          </div>
          <p style={{ fontSize: 12, color: "var(--muted-2)", margin: 0, maxWidth: 360, textAlign: "right" }}>
            Predictions are for analytics and entertainment only. Not betting advice.
          </p>
        </div>
      </footer>
    </div>
  );
}
