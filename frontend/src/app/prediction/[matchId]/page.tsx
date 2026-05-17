"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import Navbar from "@/components/Navbar";
import { PredictionSkeleton } from "@/components/LoadingSkeleton";
import ErrorState from "@/components/ErrorState";
import { getFixtureById, generatePrediction } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import type { Fixture, Prediction } from "@/lib/types";

// ── Helpers ───────────────────────────────────────────────────────────────────

function confidenceBadgeClass(level: string) {
  const c = level?.toLowerCase();
  if (c === "high") return "badge-high";
  if (c === "medium") return "badge-medium";
  return "badge-low";
}

function confidenceColor(level: string) {
  const c = level?.toLowerCase();
  if (c === "high") return "from-emerald-600 to-emerald-500";
  if (c === "medium") return "from-amber-600 to-amber-500";
  return "from-red-600 to-red-500";
}

function confidencePercent(level: string) {
  const c = level?.toLowerCase();
  if (c === "high") return 82;
  if (c === "medium") return 55;
  return 30;
}

function formatMatchTime(isoString: string): string {
  try {
    const d = new Date(
      isoString.includes("T") ? isoString : isoString.replace(" ", "T") + "Z"
    );
    return d.toLocaleDateString("en-US", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    });
  } catch {
    return isoString;
  }
}

function buildVerdictHeadline(winner: string, confidence: string): string {
  const c = confidence?.toLowerCase();
  if (c === "high") return `${winner} looks like the clear favourite`;
  if (c === "medium") return `${winner} has the edge`;
  return `${winner} slightly ahead — a tight call`;
}

function extractInsightChips(reasoning: string): Array<{ label: string; text: string }> {
  const sentences = reasoning
    .replace(/\n+/g, " ")
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 30);

  const labels = [
    "Head-to-head edge",
    "Recent matchup signal",
    "Momentum factor",
    "Model confidence",
  ];

  return sentences.slice(0, 4).map((text, i) => ({
    label: labels[i] ?? `Insight ${i + 1}`,
    text,
  }));
}

// ── Sub-components ────────────────────────────────────────────────────────────

function MatchHeaderCard({ fixture }: { fixture: Fixture }) {
  return (
    <div className="card-glass-elevated p-6 relative overflow-hidden">
      <div
        aria-hidden
        className="absolute inset-x-0 top-0 h-32 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 50% 60% at 50% 0%, rgba(124,58,237,0.15) 0%, transparent 70%)",
        }}
      />
      <div className="relative z-10">
        {/* Badges row */}
        <div className="mb-5 flex flex-wrap items-center gap-2">
          <span className="badge-sportmonks flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-blue-400" />
            SportMonks
          </span>
          <span className="badge-gemini flex items-center gap-1.5">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none">
              <path d="M13 10V3L4 14h7v7l9-11h-7z" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Gemini AI
          </span>
          {fixture._isMock && (
            <span className="badge-preview">Preview data</span>
          )}
          <span className="ml-auto text-xs text-purple-400 bg-purple-500/10 border border-purple-500/20 rounded-full px-2.5 py-0.5">
            {fixture.leagueName}
          </span>
        </div>

        {/* Teams VS layout */}
        <div className="flex items-center justify-between gap-4">
          {/* Home */}
          <div className="flex-1 text-center">
            <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-purple-900/60 to-violet-900/40 border border-purple-500/25 text-2xl font-black text-purple-200">
              {fixture.homeTeam.name.charAt(0)}
            </div>
            <p className="font-bold text-white leading-tight">{fixture.homeTeam.name}</p>
            <p className="text-xs text-gray-500 mt-0.5">Home</p>
          </div>

          {/* VS */}
          <div className="flex flex-col items-center gap-2">
            <span className="text-xs font-black text-gray-600 tracking-[0.2em]">VS</span>
            <div className="h-px w-12 bg-gradient-to-r from-transparent via-purple-500/50 to-transparent" />
          </div>

          {/* Away */}
          <div className="flex-1 text-center">
            <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-900/60 to-purple-900/40 border border-purple-500/25 text-2xl font-black text-purple-200">
              {fixture.awayTeam.name.charAt(0)}
            </div>
            <p className="font-bold text-white leading-tight">{fixture.awayTeam.name}</p>
            <p className="text-xs text-gray-500 mt-0.5">Away</p>
          </div>
        </div>

        {/* Match meta */}
        <div className="mt-5 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
              <path d="M12 6v6l4 2" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            {formatMatchTime(fixture.startingAt)}
          </span>
        </div>
      </div>
    </div>
  );
}

function AIVerdictCard({
  fixture,
  prediction,
}: {
  fixture: Fixture;
  prediction: Prediction;
}) {
  const isHome =
    prediction.winner?.toLowerCase() === fixture.homeTeam.name?.toLowerCase();
  const winner = prediction.winner || "Unknown";
  const loser = isHome ? fixture.awayTeam.name : fixture.homeTeam.name;
  const headline = buildVerdictHeadline(winner, prediction.confidence);
  const pct = prediction.winProbability ?? confidencePercent(prediction.confidence);
  const barColor = confidenceColor(prediction.confidence);

  return (
    <div className="card-glass-elevated p-8 text-center relative overflow-hidden">
      <div
        aria-hidden
        className="absolute inset-x-0 top-0 h-44 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 0%, rgba(124,58,237,0.22) 0%, transparent 70%)",
        }}
      />
      <div className="relative z-10">
        {/* AI label */}
        <div className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-purple-500/30 bg-purple-500/10 px-3 py-1">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" className="text-purple-400">
            <path d="M13 10V3L4 14h7v7l9-11h-7z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span className="text-xs font-bold uppercase tracking-widest text-purple-300">
            AI Verdict
          </span>
        </div>

        {/* Headline */}
        <p className="text-sm text-gray-400 mb-1">{headline}</p>

        {/* Winner */}
        <h2 className="text-4xl font-extrabold text-white sm:text-5xl">{winner}</h2>
        <p className="mt-1.5 text-sm text-gray-500">predicted to win over {loser}</p>

        {/* Confidence badge */}
        <div className="mt-4 flex items-center justify-center gap-2">
          <span className={confidenceBadgeClass(prediction.confidence)}>
            {prediction.confidence
              ? prediction.confidence.charAt(0).toUpperCase() + prediction.confidence.slice(1)
              : "Unknown"}{" "}
            Confidence
          </span>
        </div>

        {/* Confidence/probability bar */}
        <div className="mt-6 mx-auto max-w-xs">
          <div className="flex justify-between text-xs text-gray-500 mb-2">
            <span className="truncate max-w-[45%]">{fixture.homeTeam.name}</span>
            <span className="truncate max-w-[45%] text-right">{fixture.awayTeam.name}</span>
          </div>
          <div className="h-2.5 rounded-full bg-white/8 overflow-hidden">
            <div
              className={`h-full rounded-full bg-gradient-to-r ${barColor} transition-all duration-700`}
              style={{ width: `${Math.min(Math.max(Math.round(pct), 5), 95)}%` }}
            />
          </div>
          <p className="mt-1.5 text-center text-xs text-gray-600">
            {Math.round(pct)}% win probability
            {!prediction.winProbability && (
              <span className="text-gray-700"> (confidence-based estimate)</span>
            )}
          </p>
        </div>

        {/* Predicted score */}
        {prediction.predictedScore && (
          <div className="mt-5 inline-flex items-center gap-2 rounded-lg border border-purple-500/20 bg-purple-500/10 px-4 py-2">
            <span className="text-xs text-gray-400">Predicted score:</span>
            <span className="font-bold text-white font-mono">{prediction.predictedScore}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function ReasoningBreakdown({ reasoning }: { reasoning: string }) {
  const chips = extractInsightChips(reasoning);

  return (
    <div className="card-glass p-6">
      <h3 className="section-label mb-4">AI Reasoning Breakdown</h3>

      {chips.length > 0 ? (
        <div className="space-y-3 mb-4">
          {chips.map((chip, i) => (
            <div key={i} className="insight-chip">
              <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-purple-500/20 border border-purple-500/30">
                <span className="text-[10px] font-bold text-purple-400">{i + 1}</span>
              </div>
              <div>
                <p className="text-xs font-semibold text-purple-300 mb-0.5">{chip.label}</p>
                <p className="text-sm text-gray-300 leading-relaxed">{chip.text}</p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-300 leading-relaxed mb-4">{reasoning}</p>
      )}

      {/* Full reasoning collapsible */}
      {chips.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-xs text-gray-600 hover:text-purple-400 transition-colors select-none">
            View full reasoning ↓
          </summary>
          <p className="mt-3 text-xs text-gray-500 leading-relaxed border-t border-purple-500/10 pt-3">
            {reasoning}
          </p>
        </details>
      )}
    </div>
  );
}

function FactorList({
  title,
  items,
  accent,
}: {
  title: string;
  items: string[];
  accent: "purple" | "red";
}) {
  if (!items?.length) return null;
  const dot = accent === "purple" ? "bg-purple-400" : "bg-red-400";
  return (
    <div className="card-glass p-6">
      <h3 className="section-label mb-4">{title}</h3>
      <ul className="space-y-2">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-2.5 text-sm text-gray-300">
            <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function H2HCard({
  h2h,
  teamA,
  teamB,
}: {
  h2h: Prediction["headToHead"];
  teamA: string;
  teamB: string;
}) {
  if (!h2h) return null;
  return (
    <div className="card-glass p-6">
      <h3 className="section-label mb-4">Head to Head</h3>
      <div className="grid grid-cols-3 gap-3 text-center mb-4">
        {[
          { label: teamA, value: h2h.teamAWins, sub: "wins" },
          { label: "Draws", value: h2h.draws, sub: "" },
          { label: teamB, value: h2h.teamBWins, sub: "wins" },
        ].map(({ label, value, sub }) => (
          <div key={label} className="stat-cell">
            <p className="text-2xl font-bold text-white">{value}</p>
            <p className="text-[11px] text-gray-500 mt-0.5 truncate">
              {label} {sub}
            </p>
          </div>
        ))}
      </div>
      {h2h.recentResults && h2h.recentResults.length > 0 && (
        <div className="space-y-2">
          {h2h.recentResults.map((r, i) => (
            <div
              key={i}
              className="flex items-center justify-between rounded-lg bg-white/3 px-3 py-2 text-xs"
            >
              <span className="text-gray-400 shrink-0">{r.date}</span>
              <span className="text-gray-300 text-center flex-1 mx-3 truncate">{r.name}</span>
              <span className="text-purple-300 font-medium text-right max-w-[120px] truncate">
                {r.result_info || "—"}
              </span>
            </div>
          ))}
        </div>
      )}
      <p className="mt-3 text-right text-xs text-gray-600">{h2h.total} total matches analysed</p>
    </div>
  );
}

function PredictionSummaryPanel({
  fixture,
  prediction,
}: {
  fixture: Fixture;
  prediction: Prediction;
}) {
  return (
    <div className="card-glass p-5">
      <h3 className="section-label mb-4">Prediction Summary</h3>
      <dl className="space-y-3">
        {[
          { term: "Predicted Winner", value: prediction.winner || "Unknown" },
          {
            term: "Confidence",
            value: prediction.confidence
              ? prediction.confidence.charAt(0).toUpperCase() + prediction.confidence.slice(1)
              : "Unknown",
          },
          { term: "Match", value: fixture.name },
          { term: "League", value: fixture.leagueName },
          { term: "Fixture Source", value: fixture._isMock ? "Preview (mock)" : "SportMonks v3" },
          { term: "AI Engine", value: "Google Gemini 2.5 Flash" },
        ].map(({ term, value }) => (
          <div key={term} className="flex items-start justify-between gap-3 text-sm">
            <dt className="text-gray-500 shrink-0">{term}</dt>
            <dd className="text-white text-right font-medium">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function DataAvailabilitySection() {
  return (
    <div className="card-glass p-6 border-dashed border-purple-500/20">
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-purple-500/10 border border-purple-500/20 mt-0.5">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="text-purple-400">
            <path
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <div>
          <h4 className="font-semibold text-white text-sm mb-1">Advanced Stats</h4>
          <p className="text-xs text-gray-500 leading-relaxed">
            Advanced stats (xG, form tables, attack/defense ratings, predicted line-ups) are
            pending backend expansion. The current prediction uses SportMonks H2H and recent
            fixture context via Gemini AI.
          </p>
          <div className="mt-3 grid grid-cols-2 gap-2">
            {["xG Model", "Form Table", "Line-ups", "Player Stats"].map((item) => (
              <div
                key={item}
                className="flex items-center gap-2 rounded-lg border border-white/6 bg-white/3 px-3 py-2"
              >
                <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-600">
                  {item}
                </span>
                <span className="ml-auto text-[10px] text-gray-700">Pending</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Disclaimer() {
  return (
    <p className="text-center text-xs text-gray-700 leading-relaxed max-w-md mx-auto">
      Predictions are for analytics and entertainment only. Not betting advice. AI analysis
      generated by Google Gemini using SportMonks fixture data.
    </p>
  );
}

// ── Prediction loading state ──────────────────────────────────────────────────

function PredictLoadingState({ home, away }: { home: string; away: string }) {
  const STEPS = [
    "Reading team form",
    "Comparing attacking strength",
    "Checking defensive trends",
    "Generating AI prediction",
  ];
  const [step, setStep] = React.useState(0);

  React.useEffect(() => {
    const interval = setInterval(() => {
      setStep((s) => Math.min(STEPS.length - 1, s + 1));
    }, 520);
    return () => clearInterval(interval);
  }, []);

  return (
    <div
      style={{
        display: "flex", flexDirection: "column", alignItems: "center",
        textAlign: "center", padding: "56px 24px",
        animation: "fadeUp 0.4s cubic-bezier(0.16,1,0.3,1)",
      }}
    >
      {/* Spinning conic-gradient orb */}
      <div className="loading-orb" style={{ marginBottom: 36 }}>
        <div className="loading-orb-inner">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="currentColor" style={{ color: "var(--accent-2)" }}>
            <path d="M12 2 14 9l7 2-7 2-2 7-2-7-7-2 7-2 2-7Z" />
          </svg>
        </div>
      </div>

      <h3
        style={{
          fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em",
          color: "var(--ink)", marginBottom: 8,
        }}
      >
        Analysing {home} vs {away}
      </h3>
      <p style={{ fontSize: 14, color: "var(--muted)", marginBottom: 36, maxWidth: 400 }}>
        Gemini AI is processing head-to-head records and recent form. This may take 15–30 seconds.
      </p>

      {/* Progress steps */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10, width: "100%", maxWidth: 360 }}>
        {STEPS.map((label, i) => {
          const done = i < step;
          const active = i === step;
          return (
            <div
              key={label}
              style={{
                display: "flex", alignItems: "center", gap: 12,
                padding: "11px 16px",
                borderRadius: 12,
                background: done ? "rgba(52,211,153,0.08)" : active ? "var(--accent-soft)" : "var(--surface)",
                border: `1px solid ${done ? "rgba(52,211,153,0.2)" : active ? "var(--accent-edge)" : "var(--border)"}`,
                transition: "all 0.35s ease",
              }}
            >
              {/* Icon */}
              <div
                style={{
                  width: 22, height: 22, borderRadius: "50%", flexShrink: 0,
                  display: "grid", placeItems: "center",
                  background: done ? "#34D399" : active ? "var(--accent)" : "var(--surface-2)",
                  transition: "background 0.3s ease",
                }}
              >
                {done ? (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 6 9 17l-5-5" />
                  </svg>
                ) : active ? (
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="white" style={{ animation: "orbSpin 0.8s linear infinite" }}>
                    <path d="M12 2 14 9l7 2-7 2-2 7-2-7-7-2 7-2 2-7Z" />
                  </svg>
                ) : (
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--border-s)" }} />
                )}
              </div>
              <span
                style={{
                  fontSize: 13, fontWeight: 500,
                  color: done ? "#34D399" : active ? "var(--accent-ink)" : "var(--muted)",
                  transition: "color 0.3s ease",
                }}
              >
                {label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

type PageState =
  | "loadingFixture"
  | "ready"
  | "generating"
  | "predicted"
  | "error"
  | "unavailable";

function PredictionContent({ matchId }: { matchId: string }) {
  const { user } = useAuth();
  const router = useRouter();

  const [fixture, setFixture] = useState<Fixture | null>(null);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [pageState, setPageState] = useState<PageState>("loadingFixture");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    async function loadFixture() {
      try {
        const res = await getFixtureById(matchId);
        setFixture(res.data as Fixture);
        setPageState("ready");
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Failed to load fixture.";
        setErrorMsg(msg);
        setPageState("error");
      }
    }
    loadFixture();
  }, [matchId]);

  const handlePredict = async () => {
    if (!user || !fixture) return;
    setPageState("generating");
    setErrorMsg("");

    try {
      const token = await user.getIdToken();
      const res = await generatePrediction(matchId, token);
      const raw = res.data as Record<string, unknown>;

      const pred: Prediction = {
        winner: (raw.winner as string) || "Unknown",
        confidence: (raw.confidence as string) || "low",
        reasoning: (raw.reasoning as string) || "",
        winProbability:
          (raw.winProbability as number) ??
          (raw.win_probability as number) ??
          (raw.probability as number) ??
          undefined,
        predictedScore:
          (raw.predictedScore as string) ?? (raw.predicted_score as string) ?? undefined,
        factors: (raw.factors as string[]) ?? undefined,
        riskFactors: (raw.riskFactors as string[]) ?? undefined,
        headToHead: raw.headToHead
          ? (raw.headToHead as Prediction["headToHead"])
          : undefined,
      };

      setPrediction(pred);
      setPageState("predicted");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Prediction failed.";
      if (msg.includes("501")) {
        setErrorMsg(
          "Prediction unavailable for this fixture — real SportMonks data required."
        );
        setPageState("unavailable");
      } else {
        setErrorMsg(msg);
        setPageState("error");
      }
    }
  };

  return (
    <div className="min-h-screen">
      <Navbar />

      {/* Ambient glow */}
      <div className="relative pt-20">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-48"
          style={{
            background:
              "radial-gradient(ellipse 60% 40% at 50% 0%, rgba(124,58,237,0.12) 0%, transparent 70%)",
          }}
        />

        {/* Back link + title */}
        <div className="relative mx-auto max-w-4xl px-4 pt-10 pb-4 sm:px-6">
          <Link
            href="/dashboard"
            className="mb-4 inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-purple-400 transition-colors"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
            Back to matches
          </Link>

          {fixture && (
            <h1 className="text-2xl font-extrabold text-white sm:text-3xl">{fixture.name}</h1>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="mx-auto max-w-4xl px-4 pb-16 sm:px-6 space-y-4">
        {/* Loading fixture */}
        {pageState === "loadingFixture" && <PredictionSkeleton />}

        {/* Ready state */}
        {pageState === "ready" && fixture && (
          <div className="space-y-4">
            <MatchHeaderCard fixture={fixture} />
            <div className="card-glass p-8 flex flex-col items-center text-center gap-5">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-600/20 to-purple-600/20 border border-purple-500/30">
                <svg
                  width="28"
                  height="28"
                  viewBox="0 0 24 24"
                  fill="none"
                  className="text-purple-400"
                >
                  <path
                    d="M13 10V3L4 14h7v7l9-11h-7z"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
              <div>
                <h2 className="text-xl font-bold text-white">Ready to predict</h2>
                <p className="mt-1.5 text-sm text-gray-500 max-w-xs">
                  Gemini AI will analyse head-to-head records and recent form to generate a structured prediction.
                </p>
              </div>
              <button
                onClick={handlePredict}
                className="btn-primary text-base px-10 py-3.5"
              >
                Generate AI Prediction
              </button>
            </div>
          </div>
        )}

        {/* Generating — spinning orb + progress steps */}
        {pageState === "generating" && fixture && (
          <PredictLoadingState home={fixture.homeTeam.name} away={fixture.awayTeam.name} />
        )}

        {/* Prediction result */}
        {pageState === "predicted" && prediction && fixture && (
          <div className="space-y-4 animate-fade-in">
            {/* Match header */}
            <MatchHeaderCard fixture={fixture} />

            {/* AI Verdict hero */}
            <AIVerdictCard fixture={fixture} prediction={prediction} />

            {/* Reasoning breakdown */}
            {prediction.reasoning && (
              <ReasoningBreakdown reasoning={prediction.reasoning} />
            )}

            {/* Two-column layout on desktop: factors + summary */}
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-4">
                {prediction.factors && prediction.factors.length > 0 && (
                  <FactorList
                    title="Key Factors"
                    items={prediction.factors}
                    accent="purple"
                  />
                )}
                {prediction.riskFactors && prediction.riskFactors.length > 0 && (
                  <FactorList
                    title="Risk Factors"
                    items={prediction.riskFactors}
                    accent="red"
                  />
                )}
                {!prediction.factors?.length && !prediction.riskFactors?.length && (
                  <div className="card-glass p-6">
                    <h3 className="section-label mb-2">Key Factors</h3>
                    <p className="text-sm text-gray-600">
                      Structured factor breakdown pending backend support.
                    </p>
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <PredictionSummaryPanel fixture={fixture} prediction={prediction} />
                {prediction.headToHead && (
                  <H2HCard
                    h2h={prediction.headToHead}
                    teamA={fixture.homeTeam.name}
                    teamB={fixture.awayTeam.name}
                  />
                )}
              </div>
            </div>

            {/* Data availability notice */}
            <DataAvailabilitySection />

            {/* Regenerate */}
            <div className="text-center pt-2">
              <button onClick={handlePredict} className="btn-ghost text-sm px-6 py-2.5">
                Regenerate prediction
              </button>
            </div>

            <Disclaimer />
          </div>
        )}

        {/* Unavailable */}
        {pageState === "unavailable" && (
          <div className="card-glass p-8 flex flex-col items-center text-center gap-4 border-amber-500/20">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-amber-500/10 border border-amber-500/20">
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                className="text-amber-400"
              >
                <path
                  d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold text-white">Prediction Unavailable</h3>
              <p className="mt-2 text-sm text-gray-500 max-w-sm">
                {errorMsg ||
                  "Backend endpoint pending — real SportMonks data required for this fixture."}
              </p>
            </div>
            <Link href="/dashboard" className="btn-ghost text-sm px-6 py-2.5">
              ← Back to matches
            </Link>
          </div>
        )}

        {/* Error */}
        {pageState === "error" && (
          <ErrorState
            title="Failed to load prediction"
            message={errorMsg}
            onRetry={() => {
              if (!prediction) {
                setPageState("loadingFixture");
                router.refresh();
              } else {
                handlePredict();
              }
            }}
          />
        )}
      </div>
    </div>
  );
}

export default function PredictionPage({
  params,
}: {
  params: { matchId: string };
}) {
  return (
    <ProtectedRoute>
      <PredictionContent matchId={params.matchId} />
    </ProtectedRoute>
  );
}
