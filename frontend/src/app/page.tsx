"use client";
import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import PageLoading from "@/components/PageLoading";
import { useAuth } from "@/context/AuthContext";

// ── Static hero preview card ──────────────────────────────────────────────────

const SAMPLE_FIXTURES = [
  { league: "EPL", home: "Liverpool", away: "Man City",  status: "live", minute: "67'", conf: 72, level: "medium" },
  { league: "LIG", home: "Real Ma…", away: "Barcel…",   status: "today", time: "21:00", conf: 68, level: "medium" },
  { league: "SA",  home: "Inter Mil…", away: "AC Mil…", status: "today", time: "20:45", conf: 81, level: "high" },
];

function ConfDot({ level }: { level: string }) {
  const color = level === "high" ? "var(--primary-text)" : level === "medium" ? "var(--orange)" : "var(--muted-2)";
  return <span style={{ width: 6, height: 6, borderRadius: "50%", background: color, display: "inline-block", marginRight: 4 }} />;
}

function SoccerBallSm() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
      <path d="M2 12h20"/>
    </svg>
  );
}

function HeroPreviewCard() {
  return (
    <div style={{ position: "relative", flex: "0 0 auto", width: "min(460px, 100%)" }}>
      {/* Card */}
      <div style={{
        position: "relative",
        background: "var(--surface)",
        borderRadius: 20,
        boxShadow: "inset 0 0 0 1px var(--border-s)",
        overflow: "hidden",
      }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 20px 12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--primary)", display: "inline-block" }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)" }}>Prediction board preview</span>
          </div>
          <span style={{
            fontSize: 11, color: "var(--muted)", fontWeight: 500,
            padding: "3px 8px", borderRadius: 6,
            background: "var(--surface-2)",
            border: "1px solid var(--border)",
          }}>
            Example
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
                color: "var(--muted)", minWidth: 28, flexShrink: 0,
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
                  <><span style={{ color: "var(--primary-text)" }}>● </span>Live · {f.minute}</>
                ) : (
                  <>Today · {f.time}</>
                )}
              </span>

              {/* Confidence chip */}
              <span style={{
                fontSize: 11, fontWeight: 700,
                padding: "3px 8px", borderRadius: 20,
                background: f.level === "high" ? "var(--primary-soft)" : "var(--orange-soft)",
                color: f.level === "high" ? "var(--primary-text)" : "var(--orange)",
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
          <span style={{ fontSize: 12, color: "var(--muted)" }}>Illustrative, not real matches</span>
          <Link href="/auth" replace style={{ display: "inline-flex", alignItems: "center", minHeight: 24, fontSize: 12, color: "var(--primary-text)", fontWeight: 600, textDecoration: "none" }}>
            View all →
          </Link>
        </div>
      </div>
    </div>
  );
}

// ── Data ──────────────────────────────────────────────────────────────────────

const LEAGUES = [
  { name: "Premier League",   country: "England" },
  { name: "La Liga",          country: "Spain" },
  { name: "Serie A",          country: "Italy" },
  { name: "Bundesliga",       country: "Germany" },
  { name: "Ligue 1",          country: "France" },
  { name: "Champions League", country: "Europe" },
];

const FEATURES = [
  {
    icon: <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />,
    title: "Real match data",
    desc: "Fixtures, standings, recent results and top scorers from the football-data.org API. No scraped tables.",
    meta: "football-data.org",
  },
  {
    icon: <path d="M13 10V3L4 14h7v7l9-11h-7z" />,
    title: "AI-powered predictions",
    desc: "A Dixon-Coles model sets the probabilities, then Gemini explains them from standings, recent form and top scorers.",
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
    desc: "Premier League, La Liga, Serie A, Bundesliga, Ligue 1 and the Champions League, all in one place.",
    meta: "6 competitions",
  },
];

const STEPS = [
  { n: "01", title: "Sign in",                   desc: "Email / password or Google. Firebase Auth handles the rest." },
  { n: "02", title: "Browse upcoming matches",   desc: "Real fixtures across all six competitions, filtered by league." },
  { n: "03", title: "Generate an AI prediction", desc: "One click runs the model and asks Gemini to explain the result." },
  { n: "04", title: "Review the breakdown",      desc: "Probabilities, confidence band, reasoning and key factors." },
];

// ── Page ──────────────────────────────────────────────────────────────────────

// Every link here uses replace, so the landing page never stays in history behind a signed-in user.
function LandingPage() {
  return (
    <div style={{ minHeight: "100dvh", background: "var(--bg)", overflowX: "clip" }}>


      {/* ── Landing nav ── */}
      <header style={{
        position: "sticky", top: 0, zIndex: 40,
        paddingTop: "env(safe-area-inset-top, 0px)",
        backgroundImage: "var(--nav-bar-hero)",
      }}>
        <div style={{
          maxWidth: 1200, margin: "0 auto",
          padding: "14px clamp(16px, 4vw, 32px)",
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12,
        }}>
          {/* Brand */}
          <Link href="#" replace style={{ display: "flex", alignItems: "center", gap: 10, fontWeight: 700, fontSize: 15, color: "var(--ink)", textDecoration: "none", letterSpacing: "-0.01em", fontFamily: "var(--font-display), system-ui" }}>
            <img
              src="/future-fc-logo.svg"
              alt="FUTURE FC"
              width={36}
              height={36}
              style={{
                borderRadius: "50%",
                objectFit: "cover",
                flexShrink: 0,
                display: "block",
              }}
            />
            FUTURE FC
          </Link>

          {/* Nav links */}
          <nav style={{ alignItems: "center", gap: 4 }} className="hidden sm:flex">
            {[
              { label: "Features",     href: "#features" },
              { label: "How it works", href: "#how-it-works" },
              { label: "Leagues",      href: "#leagues" },
            ].map(({ label, href }) => (
              <Link key={href} href={href} replace className="hover-underline" style={{
                fontSize: 14, fontWeight: 600, color: "var(--ink)", padding: "6px 14px",
                borderRadius: 8, textDecoration: "none",
                transition: "color 0.15s",
              }}
              >
                {label}
              </Link>
            ))}
            <Link href="/auth" replace className="hover-underline" style={{
              fontSize: 14, fontWeight: 600, color: "var(--ink)", padding: "6px 14px",
              borderRadius: 8, textDecoration: "none",
              transition: "color 0.15s",
            }}
            >
              Sign in
            </Link>
          </nav>

          {/* CTA */}
          <Link href="/auth" replace style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            padding: "9px 18px", borderRadius: 10, fontSize: 14, fontWeight: 600,
            background: "var(--orange-gradient)",
            color: "var(--on-accent)", textDecoration: "none",
            transition: "opacity 0.15s",
          }}>
            Get started
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </Link>
        </div>
      </header>

      <main>
      {/* ── Hero ── */}
      <section className="depth" style={{ position: "relative", zIndex: 1 }}>
        <div style={{
          maxWidth: 1200, margin: "0 auto", padding: "72px clamp(16px, 4vw, 32px) 80px",
          display: "flex", alignItems: "center", gap: 64, flexWrap: "wrap",
        }}>
          {/* Left copy */}
          <div style={{ flex: "1 1 420px", minWidth: 0 }}>
            {/* Badge */}
            <div style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              padding: "5px 14px 5px 6px", borderRadius: 999,
              background: "var(--primary-soft)",
              border: "1px solid var(--primary-edge)",
              marginBottom: 28,
            }}>
              <span style={{
                width: 22, height: 22, borderRadius: "50%",
                background: "var(--primary)",
                display: "grid", placeItems: "center", color: "var(--on-accent)", fontSize: 10,
              }}>
                <SoccerBallSm />
              </span>
              <span style={{ fontSize: 12, fontWeight: 500, color: "var(--primary-text)" }}>
                Football predictions from a statistical model and AI
              </span>
            </div>

            <h1 style={{
              fontSize: "clamp(36px, 5vw, 58px)", lineHeight: 1.05,
              fontWeight: 700, letterSpacing: "-0.035em",
              color: "var(--ink)", margin: "0 0 20px",
              fontFamily: "var(--font-display), system-ui",
            }}>
              Predict football outcomes with{" "}
              <em className="sig-text" style={{ fontStyle: "normal" }}>
                real match data
              </em>
              .
            </h1>

            <p style={{ fontSize: 18, lineHeight: 1.6, color: "var(--muted)", margin: "0 0 36px", maxWidth: 500 }}>
              FUTURE FC uses fixtures, league standings, recent form and top scorers to generate
              structured predictions for the top football leagues.
            </p>

            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 28 }}>
              <Link href="/auth" replace style={{
                display: "inline-flex", alignItems: "center", gap: 8,
                padding: "14px 28px", borderRadius: 12, fontSize: 16, fontWeight: 600,
                background: "var(--primary)",
                color: "var(--on-accent)", textDecoration: "none",
              }}>
                Get started
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </Link>
              <Link href="/auth" replace style={{
                display: "inline-flex", alignItems: "center", gap: 8,
                padding: "14px 28px", borderRadius: 12, fontSize: 16, fontWeight: 600,
                background: "var(--surface)", color: "var(--ink-2)", textDecoration: "none",
                border: "1px solid var(--border-strong)",
              }}>
                View matches
              </Link>
            </div>

            {/* Trust row */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 20px" }}>
              {["No credit card", "football-data.org data", "Gemini reasoning"].map((t) => (
                <span key={t} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "var(--muted)" }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--primary-text)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
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
        <div style={{ maxWidth: 1200, margin: "0 auto", padding: "20px clamp(16px, 4vw, 32px)", display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap" }}>
          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--muted-2)", flexShrink: 0 }}>
            Covers Europe's top competitions
          </span>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {LEAGUES.map((l) => (
              <div key={l.name} style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "7px 14px", borderRadius: 999,
                background: "var(--surface-2)", border: "1px solid var(--border-strong)",
              }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--primary)", display: "inline-block" }} />
                <strong style={{ fontSize: 13, color: "var(--ink)", fontWeight: 600 }}>{l.name}</strong>
                <span style={{ fontSize: 12, color: "var(--muted)" }}>· {l.country}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section id="features" style={{ position: "relative", zIndex: 1, padding: "96px clamp(16px, 4vw, 32px)" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <header style={{ textAlign: "center", marginBottom: 56 }}>
            <div style={{
              display: "inline-block", fontSize: 11, fontWeight: 700, letterSpacing: "0.12em",
              textTransform: "uppercase", color: "var(--primary-text)",
              marginBottom: 14,
            }}>
              Why this exists
            </div>
            <h2 style={{ fontSize: "clamp(28px, 4vw, 44px)", fontWeight: 700, letterSpacing: "-0.03em", color: "var(--ink)", margin: "0 0 16px", fontFamily: "var(--font-display), system-ui" }}>
              Built for fans who want clarity, not noise.
            </h2>
            <p style={{ fontSize: 16, color: "var(--muted)", maxWidth: 560, margin: "0 auto", lineHeight: 1.6 }}>
              Four pillars run through every prediction: real match data, AI reasoning, transparent confidence and a tight focus on six competitions.
            </p>
          </header>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
            {FEATURES.map((f) => (
              <article key={f.title} className="hover-lift" style={{
                background: "var(--surface)", borderRadius: 20, padding: "28px 28px 24px",
                border: "1px solid var(--border)",
                transition: "transform 0.25s, box-shadow 0.25s",
                cursor: "default",
              }}
              >
                <div style={{
                  width: 44, height: 44, borderRadius: 12, marginBottom: 20,
                  background: "var(--primary-soft)", border: "1px solid var(--primary-edge)",
                  display: "grid", placeItems: "center", color: "var(--primary-text)",
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
        position: "relative", zIndex: 1, padding: "96px clamp(16px, 4vw, 32px)",
        background: "var(--surface)",
        borderTop: "1px solid var(--border)", borderBottom: "1px solid var(--border)",
      }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <header style={{ textAlign: "center", marginBottom: 56 }}>
            <div style={{
              display: "inline-block", fontSize: 11, fontWeight: 700, letterSpacing: "0.12em",
              textTransform: "uppercase", color: "var(--primary-text)", marginBottom: 14,
            }}>
              How it works
            </div>
            <h2 style={{ fontSize: "clamp(28px, 4vw, 44px)", fontWeight: 700, letterSpacing: "-0.03em", color: "var(--ink)", margin: 0, fontFamily: "var(--font-display), system-ui" }}>
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
                  fontFamily: "var(--font-display), monospace", fontSize: 12, fontWeight: 700, letterSpacing: "0.08em",
                  color: "var(--primary-text)", marginBottom: 14,
                  padding: "5px 10px", borderRadius: 8, display: "inline-block",
                  background: "var(--primary-soft)", border: "1px solid var(--primary-edge)",
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
      <section style={{ position: "relative", zIndex: 1, padding: "96px clamp(16px, 4vw, 32px)" }}>
        <div style={{ maxWidth: 640, margin: "0 auto", textAlign: "center" }}>
          <h2 style={{ fontSize: "clamp(28px, 4vw, 42px)", fontWeight: 700, letterSpacing: "-0.03em", color: "var(--ink)", margin: "0 0 16px", fontFamily: "var(--font-display), system-ui" }}>
            Ready to see today&apos;s board?
          </h2>
          <p style={{ fontSize: 16, color: "var(--muted)", maxWidth: 480, margin: "0 auto 32px", lineHeight: 1.6 }}>
            Sign in to access fixtures and AI predictions across all six competitions.
          </p>
          <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
            <Link href="/auth" replace style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              padding: "14px 32px", borderRadius: 12, fontSize: 16, fontWeight: 600,
              background: "var(--primary)",
              color: "var(--on-accent)", textDecoration: "none",
            }}>
              Create your account
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </Link>
            <Link href="/auth" replace style={{
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
      </main>

    </div>
  );
}

/** The landing page is for signed-out visitors. Signed-in users go to the dashboard, leaving no trace in history. */
export default function HomePage() {
  const { user, loading, signedOut } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user && !signedOut) router.replace("/dashboard");
  }, [user, loading, signedOut, router]);

  if (loading || user) return <PageLoading />;

  return <LandingPage />;
}
