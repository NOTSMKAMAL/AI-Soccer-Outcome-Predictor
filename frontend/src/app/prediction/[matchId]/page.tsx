"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import ProtectedRoute from "@/components/ProtectedRoute";
import Navbar from "@/components/Navbar";
import { PredictionSkeleton } from "@/components/LoadingSkeleton";
import ErrorState from "@/components/ErrorState";
import { getFixtureById, generatePrediction } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import type { Fixture, Prediction } from "@/lib/types";

// ── Enriched data types ───────────────────────────────────────────────────────

interface GeneralStats {
  shots_total: number | null;
  shots_on_target: number | null;
  possession: number | null;
  passes: number | null;
  pass_accuracy: number | null;
  corners: number | null;
  fouls: number | null;
  yellow_cards: number | null;
}

interface XGStats {
  xg: number | null;
  xgot: number | null;
  xpts: number | null;
  xgp: number | null;
  xgfk: number | null;
  xgc: number | null;
}

interface RecentFixture {
  fixture_id: number | null;
  name: string;
  date: string;
  home_team: { id: number | null; name: string; logo: string | null };
  away_team: { id: number | null; name: string; logo: string | null };
  score: { home: number | null; away: number | null } | null;
  result_info: string;
  participant_ids: number[];
  general_stats: { home: GeneralStats | null; away: GeneralStats | null } | null;
  xg_stats: { home: XGStats | null; away: XGStats | null } | null;
}

interface StandingRow {
  position: number;
  participant_id: number;
  team_name: string;
  team_logo: string | null;
  points: number | null;
  won: number | null;
  drawn: number | null;
  lost: number | null;
  goals_scored: number | null;
  goals_against: number | null;
  goal_difference: number | null;
  form: string | null;
}

interface TeamStats {
  goals_scored: number | null;
  goals_conceded: number | null;
  clean_sheets: number | null;
  wins: number | null;
  draws: number | null;
  losses: number | null;
  total_matches: number | null;
}

interface InjuryPlayer {
  player_name: string;
  team_id: number;
  type: string;
  reason: string;
}

interface EnrichedData {
  team_a_recent_form: RecentFixture[] | null;
  team_b_recent_form: RecentFixture[] | null;
  standings: StandingRow[] | null;
  team_a_stats: TeamStats | null;
  team_b_stats: TeamStats | null;
  injuries: { team_a: InjuryPlayer[]; team_b: InjuryPlayer[] } | null;
  xg: { team_a_xg: number; team_b_xg: number } | null;
  trends: { team_a: string[]; team_b: string[] } | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ── Shared micro-components ───────────────────────────────────────────────────

function SectionBadge({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-widest"
      style={{ borderColor: "var(--accent-edge)", background: "var(--accent-soft)", color: "var(--accent-3)" }}>
      <span className="h-1 w-1 rounded-full" style={{ background: "var(--accent-2)" }} />
      {label}
    </span>
  );
}

function SectionSkeleton({ height = 120 }: { height?: number }) {
  return <div className="card-glass animate-pulse rounded-2xl bg-white/4" style={{ height }} />;
}

function DataUnavailable() {
  return <p className="text-xs italic" style={{ color: "var(--muted-2)" }}>Data temporarily unavailable</p>;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function confidenceBadgeClass(level: string) {
  const c = level?.toLowerCase();
  if (c === "high") return "badge-high";
  if (c === "medium") return "badge-medium";
  return "badge-low";
}

function confidenceColor(level: string): string {
  const c = level?.toLowerCase();
  if (c === "high") return "from-teal-500 to-teal-400";
  if (c === "medium") return "from-amber-500 to-amber-400";
  return "from-red-500 to-red-400";
}

// Display fallback only — used when the backend returns no probability fields at all
// (i.e., hasThreeProbs is false). For all successful predictions the engine sets
// home_win_probability, draw_probability, and away_win_probability, so ThreeSegmentBar
// is shown instead and this function is never reached.
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
      weekday: "long", year: "numeric", month: "long", day: "numeric",
      hour: "numeric", minute: "2-digit", timeZoneName: "short",
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

  const labels = ["Head-to-head edge", "Recent matchup signal", "Momentum factor", "Model confidence"];
  return sentences.slice(0, 4).map((text, i) => ({ label: labels[i] ?? `Insight ${i + 1}`, text }));
}

// ── Team logo ─────────────────────────────────────────────────────────────────

function TeamLogo({ src, name, size = 64 }: { src?: string | null; name: string; size?: number }) {
  const [failed, setFailed] = useState(false);
  if (src && !failed) {
    return (
      <img src={src} alt={name} width={size} height={size}
        className="object-contain" style={{ width: size, height: size }}
        onError={() => setFailed(true)}
      />
    );
  }
  return (
    <span
      className="flex items-center justify-center rounded-2xl font-black"
      style={{
        width: size, height: size, fontSize: size * 0.4,
        background: "linear-gradient(135deg, rgba(39,90,83,0.6), rgba(19,187,175,0.3))",
        border: "1px solid rgba(19,187,175,0.25)",
        color: "var(--accent-3)",
      }}
    >
      {name.charAt(0)}
    </span>
  );
}

// ── Three-segment probability bar ─────────────────────────────────────────────

function ThreeSegmentBar({
  homeP, drawP, awayP, homeName, awayName,
}: {
  homeP: number; drawP: number; awayP: number; homeName: string; awayName: string;
}) {
  const total = homeP + drawP + awayP || 100;
  const hW = (homeP / total) * 100;
  const dW = (drawP / total) * 100;
  const aW = (awayP / total) * 100;

  return (
    <div className="mt-6 mx-auto w-full max-w-xs space-y-2">
      {/* Labels */}
      <div className="grid grid-cols-3 text-center text-xs" style={{ color: "var(--muted)" }}>
        <span className="truncate px-1 text-left">{homeName}</span>
        <span>Draw</span>
        <span className="truncate px-1 text-right">{awayName}</span>
      </div>

      {/* Bar */}
      <div className="h-3 rounded-full overflow-hidden flex gap-0.5" style={{ background: "var(--surface-2)" }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${hW}%` }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1], delay: 0.15 }}
          style={{
            height: "100%", minWidth: hW > 0 ? 6 : 0,
            background: "linear-gradient(90deg, #1A453F, #275A53)",
            borderRadius: "999px 2px 2px 999px",
          }}
        />
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${dW}%` }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1], delay: 0.3 }}
          style={{
            height: "100%", minWidth: dW > 0 ? 6 : 0,
            background: "#F8C25C",
          }}
        />
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${aW}%` }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1], delay: 0.45 }}
          style={{
            height: "100%", minWidth: aW > 0 ? 6 : 0,
            background: "linear-gradient(90deg, #4A90B0, #3A7A9A)",
            borderRadius: "2px 999px 999px 2px",
          }}
        />
      </div>

      {/* Percentages */}
      <div className="grid grid-cols-3 text-center font-bold text-sm"
        style={{ fontFamily: "var(--font-display), system-ui" }}>
        <span style={{ color: "#13BBAF" }}>{(homeP * 100).toFixed(0)}%</span>
        <span style={{ color: "#F8C25C" }}>{(drawP * 100).toFixed(0)}%</span>
        <span style={{ color: "#82B5CC" }}>{(awayP * 100).toFixed(0)}%</span>
      </div>
    </div>
  );
}

// ── MatchHeaderCard ───────────────────────────────────────────────────────────

function MatchHeaderCard({ fixture }: { fixture: Fixture }) {
  return (
    <div className="card-glass-elevated p-6 relative overflow-hidden">
      <div aria-hidden className="absolute inset-x-0 top-0 h-32 pointer-events-none" style={{
        background: "radial-gradient(ellipse 50% 60% at 50% 0%, rgba(39,90,83,0.22) 0%, transparent 70%)",
      }} />
      <div className="relative z-10">
        {/* Badges */}
        <div className="mb-5 flex flex-wrap items-center gap-2">
          <span className="badge-football-data flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: "var(--accent-2)" }} />
            football-data.org
          </span>
          <span className="badge-gemini flex items-center gap-1.5">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none">
              <path d="M13 10V3L4 14h7v7l9-11h-7z" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Gemini AI
          </span>
          {fixture._isMock && <span className="badge-preview">Preview data</span>}
          <span className="ml-auto text-xs rounded-full px-2.5 py-0.5" style={{ color: "var(--warm)", background: "var(--warm-bg)", border: "1px solid rgba(248,194,92,0.2)" }}>
            {fixture.leagueName}
          </span>
        </div>

        {/* Teams VS */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1 text-center">
            <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center">
              <TeamLogo src={fixture.homeTeam.logo} name={fixture.homeTeam.name} size={64} />
            </div>
            <p className="font-bold leading-tight" style={{ color: "var(--ink)" }}>{fixture.homeTeam.name}</p>
            <p className="text-xs mt-0.5" style={{ color: "var(--muted-2)" }}>Home</p>
          </div>
          <div className="flex flex-col items-center gap-2">
            <span className="text-xs font-black tracking-[0.2em]" style={{ color: "var(--muted-2)" }}>VS</span>
            <div className="h-px w-12" style={{ background: "linear-gradient(to right, transparent, var(--accent-edge), transparent)" }} />
          </div>
          <div className="flex-1 text-center">
            <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center">
              <TeamLogo src={fixture.awayTeam.logo} name={fixture.awayTeam.name} size={64} />
            </div>
            <p className="font-bold leading-tight" style={{ color: "var(--ink)" }}>{fixture.awayTeam.name}</p>
            <p className="text-xs mt-0.5" style={{ color: "var(--muted-2)" }}>Away</p>
          </div>
        </div>

        {/* Match meta */}
        <div className="mt-5 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs" style={{ color: "var(--muted)" }}>
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

// ── AIVerdictCard — three-segment probability bar ─────────────────────────────

function AIVerdictCard({
  fixture,
  prediction,
}: {
  fixture: Fixture;
  prediction: Prediction;
}) {
  const isHome = prediction.winner?.toLowerCase() === fixture.homeTeam.name?.toLowerCase();
  const winner = prediction.winner || "Unknown";
  const loser = isHome ? fixture.awayTeam.name : fixture.homeTeam.name;
  const headline = buildVerdictHeadline(winner, prediction.confidence);
  const barColor = confidenceColor(prediction.confidence);

  // Three-segment bar data
  const hasThreeProbs =
    prediction.home_win_probability != null &&
    prediction.draw_probability != null &&
    prediction.away_win_probability != null;

  const homeP = prediction.home_win_probability ?? 0;
  const drawP = prediction.draw_probability ?? 0;
  const awayP = prediction.away_win_probability ?? 0;

  // Fallback single-segment bar — only shown when hasThreeProbs is false.
  // prediction.winProbability is not set by the engine; confidencePercent() is the
  // last-resort estimate. In practice hasThreeProbs is always true for successful
  // predictions because the engine sets all three probability fields in both the
  // Dixon-Coles path (dc_probs) and the confidence-estimate fallback path.
  const pct = prediction.winProbability ?? confidencePercent(prediction.confidence);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="card-glass-elevated p-8 text-center relative overflow-hidden"
    >
      <div aria-hidden className="absolute inset-x-0 top-0 h-44 pointer-events-none" style={{
        background: "radial-gradient(ellipse 60% 50% at 50% 0%, rgba(19,187,175,0.18) 0%, transparent 70%)",
      }} />

      <div className="relative z-10">
        {/* AI Verdict badge */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.1, duration: 0.4 }}
          className="mb-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1"
          style={{ border: "1px solid var(--accent-edge)", background: "var(--accent-soft)" }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" style={{ color: "var(--accent-2)" }}>
            <path d="M13 10V3L4 14h7v7l9-11h-7z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span className="text-xs font-bold uppercase tracking-widest" style={{ color: "var(--accent-3)" }}>
            AI Verdict
          </span>
        </motion.div>

        <p className="text-sm mb-1" style={{ color: "var(--muted)" }}>{headline}</p>

        <motion.h2
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="text-4xl font-extrabold sm:text-5xl"
          style={{ color: "var(--ink)", fontFamily: "var(--font-display), system-ui", letterSpacing: "-0.02em" }}
        >
          {winner}
        </motion.h2>

        <p className="mt-1.5 text-sm" style={{ color: "var(--muted-2)" }}>predicted to win over {loser}</p>

        <div className="mt-4 flex items-center justify-center gap-2">
          <span className={confidenceBadgeClass(prediction.confidence)}>
            {prediction.confidence
              ? prediction.confidence.charAt(0).toUpperCase() + prediction.confidence.slice(1)
              : "Unknown"}{" "}
            Confidence
          </span>
        </div>

        {/* ── Three-segment bar (primary) — uses actual Dixon-Coles probabilities ── */}
        {hasThreeProbs ? (
          <ThreeSegmentBar
            homeP={homeP}
            drawP={drawP}
            awayP={awayP}
            homeName={fixture.homeTeam.name}
            awayName={fixture.awayTeam.name}
          />
        ) : (
          /* Fallback single-segment bar — shown only when all three probability
             fields are missing from the API response (should not occur in practice) */
          <div className="mt-6 mx-auto max-w-xs">
            <div className="flex justify-between text-xs mb-2" style={{ color: "var(--muted)" }}>
              <span className="truncate max-w-[45%]">{fixture.homeTeam.name}</span>
              <span className="truncate max-w-[45%] text-right">{fixture.awayTeam.name}</span>
            </div>
            <div className="h-2.5 rounded-full overflow-hidden" style={{ background: "var(--surface-2)" }}>
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${Math.min(Math.max(Math.round(pct), 5), 95)}%` }}
                transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1], delay: 0.3 }}
                className={`h-full rounded-full bg-gradient-to-r ${barColor}`}
              />
            </div>
            <p className="mt-1.5 text-center text-xs" style={{ color: "var(--muted-2)" }}>
              {Math.round(pct)}% win probability
              {!prediction.winProbability && <span style={{ color: "var(--muted-2)" }}> (confidence-based estimate)</span>}
            </p>
          </div>
        )}
      </div>
    </motion.div>
  );
}

// ── H2H Timeline ──────────────────────────────────────────────────────────────

function H2HTimeline({ h2h, teamA, teamB }: { h2h: Prediction["headToHead"]; teamA: string; teamB: string }) {
  if (!h2h) return null;

  function resultBadge(result_info: string): { label: string; cls: string } {
    const ri = (result_info || "").toLowerCase();
    if (teamA.toLowerCase().split(" ").some((w) => ri.includes(w)) && ri.includes("won"))
      return { label: "W", cls: "bg-teal-500/20 text-teal-400 border-teal-500/30" };
    if (teamB.toLowerCase().split(" ").some((w) => ri.includes(w)) && ri.includes("won"))
      return { label: "L", cls: "bg-red-500/20 text-red-400 border-red-500/30" };
    return { label: "D", cls: "bg-amber-500/20 text-amber-400 border-amber-500/30" };
  }

  function rowBorder(result_info: string) {
    const ri = (result_info || "").toLowerCase();
    if (teamA.toLowerCase().split(" ").some((w) => ri.includes(w)) && ri.includes("won"))
      return "border-l-teal-500/50";
    if (teamB.toLowerCase().split(" ").some((w) => ri.includes(w)) && ri.includes("won"))
      return "border-l-red-500/50";
    return "border-l-amber-500/50";
  }

  return (
    <div className="card-glass p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="section-label">Head to Head History</h3>
        <SectionBadge label="HISTORICAL DATA • football-data.org" />
      </div>
      <div className="flex gap-6 mb-4 text-center">
        {[
          { val: h2h.teamAWins, label: teamA },
          { val: h2h.draws, label: "Draws" },
          { val: h2h.teamBWins, label: teamB },
        ].map(({ val, label }) => (
          <div key={label} className="stat-cell flex-1">
            <p className="text-2xl font-bold" style={{ color: "var(--ink)", fontFamily: "var(--font-display), system-ui" }}>{val}</p>
            <p className="text-[11px] mt-0.5 truncate" style={{ color: "var(--muted)" }}>{label}</p>
          </div>
        ))}
      </div>
      {(h2h.recentResults || []).length > 0 && (
        <div className="space-y-2 mt-4">
          {(h2h.recentResults || []).map((r, i) => {
            const badge = resultBadge(r.result_info);
            return (
              <div key={i} className={`flex items-center gap-3 rounded-lg border-l-2 px-3 py-2.5 text-xs ${rowBorder(r.result_info)}`}
                style={{ background: "rgba(255,255,255,0.025)" }}>
                <span className="shrink-0 w-20" style={{ color: "var(--muted)" }}>{r.date}</span>
                <span className="flex-1 truncate" style={{ color: "var(--ink-2)" }}>{r.name}</span>
                <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold ${badge.cls}`}>
                  {badge.label}
                </span>
              </div>
            );
          })}
        </div>
      )}
      <p className="mt-3 text-right text-xs" style={{ color: "var(--muted-2)" }}>{h2h.total} total matches</p>
    </div>
  );
}

// ── Recent Form ───────────────────────────────────────────────────────────────

function SplitBar({ homeVal, awayVal, redBars = false }: { homeVal: number | null; awayVal: number | null; redBars?: boolean }) {
  const h = homeVal ?? 0;
  const a = awayVal ?? 0;
  const total = h + a;
  const homeW = total > 0 ? (h / total) * 100 : 50;
  const awayW = total > 0 ? (a / total) * 100 : 50;
  const homeColor = redBars ? "#ef4444" : "#275A53";
  const awayColor = redBars ? "#ef4444" : "#13BBAF";
  return (
    <div className="flex w-full h-1.5 rounded-full overflow-hidden mt-1">
      <div style={{ width: `${homeW}%`, background: homeColor, transition: "width 0.4s ease" }} />
      <div style={{ width: `${awayW}%`, background: awayColor, transition: "width 0.4s ease" }} />
    </div>
  );
}

function StatRow({ name, homeVal, awayVal, fmt = String, redBars = false }: {
  name: string; homeVal: number | null; awayVal: number | null;
  fmt?: (v: number) => string; redBars?: boolean;
}) {
  return (
    <div className="mb-3">
      <div className="flex items-baseline justify-between">
        <span className="text-sm w-12 text-left font-medium" style={{ color: "var(--ink-2)" }}>
          {homeVal != null ? fmt(homeVal) : "—"}
        </span>
        <span className="text-xs italic flex-1 text-center" style={{ color: "var(--muted)" }}>{name}</span>
        <span className="text-sm w-12 text-right font-medium" style={{ color: "var(--ink-2)" }}>
          {awayVal != null ? fmt(awayVal) : "—"}
        </span>
      </div>
      {(homeVal != null || awayVal != null) && (
        <SplitBar homeVal={homeVal} awayVal={awayVal} redBars={redBars} />
      )}
    </div>
  );
}

function GeneralStatsTab({ myStats, oppStats }: { myStats: GeneralStats | null; oppStats: GeneralStats | null }) {
  if (!myStats && !oppStats) return <p className="text-xs italic py-2" style={{ color: "var(--muted-2)" }}>Match stats not available</p>;
  const pct = (v: number) => `${v}%`;
  return (
    <div className="pt-2">
      <StatRow name="Shots Total"     homeVal={myStats?.shots_total ?? null}     awayVal={oppStats?.shots_total ?? null} />
      <StatRow name="Shots On Target" homeVal={myStats?.shots_on_target ?? null} awayVal={oppStats?.shots_on_target ?? null} />
      <StatRow name="Possession"      homeVal={myStats?.possession ?? null}      awayVal={oppStats?.possession ?? null}  fmt={pct} />
      <StatRow name="Passes"          homeVal={myStats?.passes ?? null}          awayVal={oppStats?.passes ?? null} />
      <StatRow name="Pass Accuracy"   homeVal={myStats?.pass_accuracy ?? null}   awayVal={oppStats?.pass_accuracy ?? null} fmt={pct} />
      <StatRow name="Corners"         homeVal={myStats?.corners ?? null}         awayVal={oppStats?.corners ?? null} />
      <StatRow name="Fouls"           homeVal={myStats?.fouls ?? null}           awayVal={oppStats?.fouls ?? null} />
      <StatRow name="Yellow Cards"    homeVal={myStats?.yellow_cards ?? null}    awayVal={oppStats?.yellow_cards ?? null} redBars />
    </div>
  );
}

function MatchCardInner({ fixture, teamId, defaultExpanded }: { fixture: RecentFixture; teamId: number; defaultExpanded: boolean }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const isHome  = fixture.home_team.id === teamId;
  const myTeam  = isHome ? fixture.home_team  : fixture.away_team;
  const oppTeam = isHome ? fixture.away_team  : fixture.home_team;
  const myGeneral  = isHome ? fixture.general_stats?.home : fixture.general_stats?.away;
  const oppGeneral = isHome ? fixture.general_stats?.away : fixture.general_stats?.home;
  const myScore  = isHome ? fixture.score?.home : fixture.score?.away;
  const oppScore = isHome ? fixture.score?.away : fixture.score?.home;
  const scoreStr = myScore != null && oppScore != null ? `${myScore} — ${oppScore}` : "vs";
  const ri = (fixture.result_info || "").toLowerCase();
  let resultLabel: "W" | "D" | "L" = "L";
  let resultCls = "bg-red-500/20 text-red-400 border-red-500/30";
  if (myTeam.name.toLowerCase().split(" ").some((w) => ri.includes(w)) && ri.includes("won")) {
    resultLabel = "W"; resultCls = "bg-teal-500/20 text-teal-400 border-teal-500/30";
  } else if (ri.includes("draw") || ri.includes("drew")) {
    resultLabel = "D"; resultCls = "bg-amber-500/20 text-amber-400 border-amber-500/30";
  }

  return (
    <div className="rounded-xl overflow-hidden mb-2" style={{ border: "1px solid var(--border)", background: "rgba(255,255,255,0.025)" }}>
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center gap-2 px-4 py-3 text-left transition-colors"
        style={{ cursor: "pointer" }}
        onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "rgba(255,255,255,0.04)")}
        onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "transparent")}
      >
        <TeamLogo src={myTeam.logo}  name={myTeam.name}  size={24} />
        <span className="text-xs flex-1 truncate" style={{ color: "var(--ink-2)" }}>{myTeam.name}</span>
        <span className="text-sm font-bold px-2 shrink-0" style={{ color: "var(--ink)" }}>{scoreStr}</span>
        <span className="text-xs flex-1 text-right truncate" style={{ color: "var(--ink-2)" }}>{oppTeam.name}</span>
        <TeamLogo src={oppTeam.logo} name={oppTeam.name} size={24} />
        <span className={`ml-2 shrink-0 rounded-full border px-1.5 py-0.5 text-[9px] font-bold ${resultCls}`}>{resultLabel}</span>
        <span className="text-[10px] ml-1 shrink-0" style={{ color: "var(--muted-2)" }}>{fixture.date}</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          className={`ml-1 transition-transform ${expanded ? "rotate-180" : ""}`} style={{ color: "var(--muted-2)" }}>
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {expanded && (
        <div className="px-4 pb-4">
          <div className="flex items-center justify-between py-2 mb-1" style={{ borderTop: "1px solid var(--border)" }}>
            <TeamLogo src={myTeam.logo}  name={myTeam.name}  size={32} />
            <span className="text-xs font-bold tracking-wide" style={{ color: "var(--ink-2)" }}>Statistics</span>
            <TeamLogo src={oppTeam.logo} name={oppTeam.name} size={32} />
          </div>
          <GeneralStatsTab myStats={myGeneral ?? null} oppStats={oppGeneral ?? null} />
        </div>
      )}
    </div>
  );
}

function RecentFormSection({ formA, formB, teamA, teamB, teamAId, teamBId }: {
  formA: RecentFixture[] | null; formB: RecentFixture[] | null;
  teamA: string; teamB: string; teamAId: number; teamBId: number;
}) {
  return (
    <div className="card-glass p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="section-label">Recent Form</h3>
        <SectionBadge label="SCHEDULES & RESULTS • football-data.org" />
      </div>
      <div className="grid grid-cols-2 gap-4">
        {[
          { name: teamA, fixtures: formA, tid: teamAId },
          { name: teamB, fixtures: formB, tid: teamBId },
        ].map(({ name, fixtures, tid }) => (
          <div key={name}>
            <p className="text-xs font-semibold mb-2 truncate" style={{ color: "var(--muted)" }}>{name}</p>
            {fixtures && fixtures.length > 0 ? (
              fixtures.map((f, i) => (
                <MatchCardInner key={f.fixture_id ?? i} fixture={f} teamId={tid} defaultExpanded={i === 0} />
              ))
            ) : (
              <DataUnavailable />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── xG Analysis ───────────────────────────────────────────────────────────────

function XGSection({ xg, teamA, teamB }: { xg: { team_a_xg: number; team_b_xg: number } | null; teamA: string; teamB: string }) {
  if (!xg) return null;
  const max = Math.max(xg.team_a_xg, xg.team_b_xg, 0.01);
  const pctA = Math.round((xg.team_a_xg / max) * 100);
  const pctB = Math.round((xg.team_b_xg / max) * 100);
  const diff = Math.abs(xg.team_a_xg - xg.team_b_xg).toFixed(2);
  const leader = xg.team_a_xg > xg.team_b_xg ? teamA : teamB;

  return (
    <div className="card-glass p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="section-label">xG Match Analysis</h3>
        <SectionBadge label="EXPECTED GOALS (xG) • football-data.org" />
      </div>
      <p className="text-xs mb-5" style={{ color: "var(--muted)" }}>
        xG = Expected Goals — measures quality of chances regardless of scoreline.
      </p>
      <div className="space-y-4">
        {[
          { name: teamA, xgVal: xg.team_a_xg, pct: pctA, color: "#275A53" },
          { name: teamB, xgVal: xg.team_b_xg, pct: pctB, color: "#13BBAF" },
        ].map(({ name, xgVal, pct, color }) => (
          <div key={name}>
            <div className="flex justify-between text-xs mb-1.5">
              <span className="truncate max-w-[60%]" style={{ color: "var(--ink-2)" }}>{name}</span>
              <span className="font-bold" style={{ color: "var(--ink)", fontFamily: "var(--font-display), system-ui" }}>{xgVal.toFixed(2)} xG</span>
            </div>
            <div className="h-3 rounded-full overflow-hidden" style={{ background: "var(--surface-2)" }}>
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                className="h-full rounded-full"
                style={{ background: color }}
              />
            </div>
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs" style={{ color: "var(--accent-3)" }}>
        {leader} created {diff} more xG — created better scoring chances
      </p>
    </div>
  );
}

// ── Injuries & Suspensions ────────────────────────────────────────────────────

function InjurySection({ injuries, teamA, teamB }: { injuries: { team_a: InjuryPlayer[]; team_b: InjuryPlayer[] } | null; teamA: string; teamB: string }) {
  function InjuryList({ players, label }: { players: InjuryPlayer[]; label: string }) {
    return (
      <div>
        <p className="text-xs font-semibold mb-2 truncate" style={{ color: "var(--muted)" }}>{label}</p>
        {players.length === 0 ? (
          <p className="text-xs" style={{ color: "var(--accent-2)" }}>✅ Full squad available</p>
        ) : (
          <div className="space-y-1.5">
            {players.map((p, i) => {
              const isSusp = p.type?.toLowerCase().includes("suspend");
              return (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span>{isSusp ? "🟡" : "🔴"}</span>
                  <span className="flex-1 truncate" style={{ color: "var(--ink-2)" }}>{p.player_name}</span>
                  <span className={`shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold uppercase ${isSusp ? "bg-amber-500/20 text-amber-400" : "bg-red-500/20 text-red-400"}`}>
                    {isSusp ? "SUSP" : "INJ"}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="card-glass p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="section-label">Injuries &amp; Suspensions</h3>
        <SectionBadge label="INJURIES & SUSPENSIONS • football-data.org" />
      </div>
      {!injuries ? <DataUnavailable /> : (
        <div className="grid grid-cols-2 gap-6">
          <InjuryList players={injuries.team_a} label={teamA} />
          <InjuryList players={injuries.team_b} label={teamB} />
        </div>
      )}
    </div>
  );
}

// ── Season Stats ──────────────────────────────────────────────────────────────

function StatBar({ label, valA, valB, nameA, nameB, invert = false }: {
  label: string; valA: number | null; valB: number | null;
  nameA: string; nameB: string; invert?: boolean;
}) {
  const a = valA ?? 0;
  const b = valB ?? 0;
  const max = Math.max(a, b, 1);
  const pA = Math.round((a / max) * 100);
  const pB = Math.round((b / max) * 100);
  const barA = invert ? "#ef4444" : "#275A53";
  const barB = invert ? "#ef4444" : "#13BBAF";

  return (
    <div className="mb-4">
      <p className="text-xs mb-1.5" style={{ color: "var(--muted)" }}>{label}</p>
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <div className="flex justify-between text-xs mb-1">
            <span className="truncate max-w-[60%]" style={{ color: "var(--muted)" }}>{nameA}</span>
            <span className="font-bold" style={{ color: "var(--ink)" }}>{valA ?? "—"}</span>
          </div>
          <div className="h-2 rounded-full overflow-hidden" style={{ background: "var(--surface-2)" }}>
            <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pA}%`, background: barA }} />
          </div>
        </div>
        <div className="flex-1">
          <div className="flex justify-between text-xs mb-1">
            <span className="font-bold" style={{ color: "var(--ink)" }}>{valB ?? "—"}</span>
            <span className="truncate max-w-[60%] text-right" style={{ color: "var(--muted)" }}>{nameB}</span>
          </div>
          <div className="h-2 rounded-full overflow-hidden" style={{ background: "var(--surface-2)" }}>
            <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pB}%`, background: barB }} />
          </div>
        </div>
      </div>
    </div>
  );
}

function SeasonStatsSection({ statsA, statsB, teamA, teamB }: { statsA: TeamStats | null; statsB: TeamStats | null; teamA: string; teamB: string }) {
  const noData = !statsA && !statsB;
  const totalA = statsA?.total_matches || 1;
  const totalB = statsB?.total_matches || 1;
  const wrA = statsA?.wins != null ? Math.round((statsA.wins / totalA) * 100) : null;
  const wrB = statsB?.wins != null ? Math.round((statsB.wins / totalB) * 100) : null;

  return (
    <div className="card-glass p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="section-label">Season Statistics</h3>
        <SectionBadge label="STATISTICS • football-data.org" />
      </div>
      {noData ? <DataUnavailable /> : (
        <>
          <StatBar label="Goals Scored"   valA={statsA?.goals_scored ?? null}   valB={statsB?.goals_scored ?? null}   nameA={teamA} nameB={teamB} />
          <StatBar label="Goals Conceded" valA={statsA?.goals_conceded ?? null} valB={statsB?.goals_conceded ?? null} nameA={teamA} nameB={teamB} invert />
          <StatBar label="Clean Sheets"   valA={statsA?.clean_sheets ?? null}   valB={statsB?.clean_sheets ?? null}   nameA={teamA} nameB={teamB} />
          <StatBar label="Win Rate (%)"   valA={wrA} valB={wrB} nameA={teamA} nameB={teamB} />
        </>
      )}
    </div>
  );
}

// ── League Standings ──────────────────────────────────────────────────────────

function StandingsSection({ standings, teamAId, teamBId }: { standings: StandingRow[] | null; teamAId: number; teamBId: number }) {
  if (!standings || standings.length === 0) return null;

  const posA = standings.findIndex((r) => r.participant_id === teamAId);
  const posB = standings.findIndex((r) => r.participant_id === teamBId);
  const topIdx = Math.min(posA < 0 ? 999 : posA, posB < 0 ? 999 : posB);
  const botIdx = Math.max(posA < 0 ? -1 : posA, posB < 0 ? -1 : posB);
  const start = Math.max(0, topIdx - 3);
  const end = Math.min(standings.length, botIdx + 4);
  const slice = standings.slice(start, end);

  return (
    <div className="card-glass p-6 overflow-x-auto">
      <div className="flex items-center justify-between mb-4">
        <h3 className="section-label">League Standings</h3>
        <SectionBadge label="STANDINGS • football-data.org" />
      </div>
      <table className="w-full text-xs" style={{ color: "var(--muted)" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border)" }}>
            {["#", "Team", "P", "W", "D", "L", "GD", "Pts"].map((h) => (
              <th key={h} className={`pb-2 font-semibold ${h === "Team" ? "text-left pl-2" : "text-center"}`}
                style={{ color: "var(--muted-2)" }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {slice.map((row) => {
            const isHighlighted = row.participant_id === teamAId || row.participant_id === teamBId;
            return (
              <tr key={row.participant_id}
                className={`border-l-2 transition-colors ${isHighlighted ? "border-l-teal-500" : "border-l-transparent"}`}
                style={{ background: isHighlighted ? "rgba(19,187,175,0.07)" : "transparent" }}
              >
                <td className="py-2 text-center font-mono">{row.position}</td>
                <td className="py-2 pl-2 text-left">
                  <span style={{ color: isHighlighted ? "var(--ink)" : "var(--ink-2)", fontWeight: isHighlighted ? 600 : 400 }}>
                    {row.team_name || "—"}
                  </span>
                </td>
                {[
                  (row.won ?? 0) + (row.drawn ?? 0) + (row.lost ?? 0),
                  row.won, row.drawn, row.lost, row.goal_difference, row.points,
                ].map((val, i) => (
                  <td key={i} className="py-2 text-center font-mono">{val ?? "—"}</td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── Trends ────────────────────────────────────────────────────────────────────

const TREND_EMOJI: Record<string, string> = {
  scoring: "🔥", score: "🔥", goal: "⚽", clean: "🧱", unbeaten: "📈", btts: "⚽", win: "🏆", form: "📊",
};
function trendEmoji(label: string): string {
  const lower = label.toLowerCase();
  for (const [key, emoji] of Object.entries(TREND_EMOJI)) { if (lower.includes(key)) return emoji; }
  return "📌";
}

function TrendsSection({ trends, teamA, teamB }: { trends: { team_a: string[]; team_b: string[] } | null; teamA: string; teamB: string }) {
  const hasAny = (trends?.team_a?.length ?? 0) > 0 || (trends?.team_b?.length ?? 0) > 0;
  if (!trends || !hasAny) return null;

  return (
    <div className="card-glass p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="section-label">Current Trends</h3>
        <SectionBadge label="LIVESCORES & EVENTS • football-data.org" />
      </div>
      <div className="grid grid-cols-2 gap-6">
        {[{ name: teamA, items: trends.team_a }, { name: teamB, items: trends.team_b }].map(({ name, items }) => (
          <div key={name}>
            <p className="text-xs font-semibold mb-2 truncate" style={{ color: "var(--muted)" }}>{name}</p>
            {items.length === 0 ? (
              <p className="text-xs" style={{ color: "var(--muted-2)" }}>No trend data</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {items.map((t, i) => (
                  <span key={i} className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs"
                    style={{ border: "1px solid var(--accent-edge)", background: "var(--accent-soft)", color: "var(--accent-3)" }}>
                    {trendEmoji(t)} {t}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Reasoning & Key Factors ───────────────────────────────────────────────────

function ReasoningBreakdown({ reasoning }: { reasoning: string }) {
  const chips = extractInsightChips(reasoning);
  return (
    <div className="card-glass p-6">
      <h3 className="section-label mb-4">AI Reasoning Breakdown</h3>
      {chips.length > 0 ? (
        <div className="space-y-3 mb-4">
          {chips.map((chip, i) => (
            <div key={i} className="insight-chip">
              <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md"
                style={{ background: "var(--accent-soft)", border: "1px solid var(--accent-edge)" }}>
                <span className="text-[10px] font-bold" style={{ color: "var(--accent-2)" }}>{i + 1}</span>
              </div>
              <div>
                <p className="text-xs font-semibold mb-0.5" style={{ color: "var(--accent-3)" }}>{chip.label}</p>
                <p className="text-sm leading-relaxed" style={{ color: "var(--ink-2)" }}>{chip.text}</p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm leading-relaxed mb-4" style={{ color: "var(--ink-2)" }}>{reasoning}</p>
      )}
      {chips.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-xs transition-colors select-none"
            style={{ color: "var(--muted-2)" }}
            onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = "var(--accent-3)")}
            onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = "var(--muted-2)")}
          >
            View full reasoning ↓
          </summary>
          <p className="mt-3 text-xs leading-relaxed pt-3" style={{ color: "var(--muted)", borderTop: "1px solid var(--border)" }}>
            {reasoning}
          </p>
        </details>
      )}
    </div>
  );
}

function KeyFactorsList({ keyFactors }: { keyFactors: Array<{ title: string; text: string }> }) {
  if (!keyFactors || keyFactors.length === 0) return null;
  return (
    <div className="card-glass p-6">
      <h3 className="section-label mb-4">Key Factors</h3>
      <div className="space-y-3">
        {keyFactors.map((kf, i) => (
          <div key={i} className="flex items-start gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-[10px] font-bold"
              style={{ background: "var(--brand-soft)", border: "1px solid rgba(39,90,83,0.3)", color: "var(--accent-2)" }}>
              {i + 1}
            </span>
            <div>
              <p className="text-xs font-semibold mb-0.5" style={{ color: "var(--accent-3)" }}>{kf.title}</p>
              <p className="text-sm leading-relaxed" style={{ color: "var(--ink-2)" }}>{kf.text}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PredictionSummaryPanel({ fixture, prediction }: { fixture: Fixture; prediction: Prediction }) {
  return (
    <div className="card-glass p-5">
      <h3 className="section-label mb-4">Prediction Summary</h3>
      <dl className="space-y-3">
        {[
          { term: "Predicted Winner", value: prediction.winner || "Unknown" },
          { term: "Confidence", value: prediction.confidence ? prediction.confidence.charAt(0).toUpperCase() + prediction.confidence.slice(1) : "Unknown" },
          { term: "Match", value: fixture.name },
          { term: "League", value: fixture.leagueName },
          { term: "Fixture Source", value: fixture._isMock ? "Preview (mock)" : "football-data.org" },
          { term: "AI Engine", value: "Google Gemini 2.5 Flash" },
        ].map(({ term, value }) => (
          <div key={term} className="flex items-start justify-between gap-3 text-sm">
            <dt style={{ color: "var(--muted)", flexShrink: 0 }}>{term}</dt>
            <dd className="text-right font-medium" style={{ color: "var(--ink)" }}>{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function DataAvailabilitySection() {
  return (
    <div className="card-glass p-6 border-dashed" style={{ borderColor: "var(--accent-edge)" }}>
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg mt-0.5"
          style={{ background: "var(--accent-soft)", border: "1px solid var(--accent-edge)" }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ color: "var(--accent-2)" }}>
            <path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <div>
          <h4 className="font-semibold text-sm mb-1" style={{ color: "var(--ink)" }}>Advanced Stats</h4>
          <p className="text-xs leading-relaxed" style={{ color: "var(--muted)" }}>
            xG, form tables, standings, injuries, and top scorers are sourced live from football-data.org. Player stats and predicted line-ups pending backend expansion.
          </p>
        </div>
      </div>
    </div>
  );
}

function Disclaimer() {
  return (
    <p className="text-center text-xs leading-relaxed max-w-md mx-auto" style={{ color: "var(--muted-2)" }}>
      Predictions are for analytics and entertainment only. Not betting advice. AI analysis generated by Google Gemini using football-data.org fixture data.
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
    <div style={{ display:"flex", flexDirection:"column", alignItems:"center", textAlign:"center", padding:"56px 24px", animation:"fadeUp 0.4s cubic-bezier(0.16,1,0.3,1)" }}>
      <div className="loading-orb" style={{ marginBottom: 36 }}>
        <div className="loading-orb-inner">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color:"var(--accent-2)" }}>
            <circle cx="12" cy="12" r="10"/>
            <path d="M12 2a10 10 0 0 0-6.88 2.77L12 12l7.47-4.5A10 10 0 0 0 12 2z" fill="currentColor" fillOpacity="0.4"/>
          </svg>
        </div>
      </div>
      <h3 style={{ fontSize:22, fontWeight:600, letterSpacing:"-0.02em", color:"var(--ink)", marginBottom:8, fontFamily:"var(--font-display), system-ui" }}>
        Analysing {home} vs {away}
      </h3>
      <p style={{ fontSize:14, color:"var(--muted)", marginBottom:36, maxWidth:400 }}>
        Gemini AI is processing head-to-head records, standings, xG data and recent form. This may take 20–40 seconds.
      </p>
      <div style={{ display:"flex", flexDirection:"column", gap:10, width:"100%", maxWidth:360 }}>
        {STEPS.map((label, i) => {
          const done = i < step;
          const active = i === step;
          return (
            <div key={label} style={{
              display:"flex", alignItems:"center", gap:12, padding:"11px 16px", borderRadius:12,
              background: done ? "rgba(19,187,175,0.08)" : active ? "var(--accent-soft)" : "var(--surface)",
              border: `1px solid ${done ? "rgba(19,187,175,0.22)" : active ? "var(--accent-edge)" : "var(--border)"}`,
              transition:"all 0.35s ease",
            }}>
              <div style={{
                width:22, height:22, borderRadius:"50%", flexShrink:0, display:"grid", placeItems:"center",
                background: done ? "#13BBAF" : active ? "var(--accent)" : "var(--surface-2)",
                transition:"background 0.3s ease",
              }}>
                {done ? (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#020E0C" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
                ) : active ? (
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="white" style={{ animation:"orbSpin 0.8s linear infinite" }}><path d="M12 2 14 9l7 2-7 2-2 7-2-7-7-2 7-2 2-7Z" /></svg>
                ) : (
                  <span style={{ width:6, height:6, borderRadius:"50%", background:"var(--border-s)" }} />
                )}
              </div>
              <span style={{ fontSize:13, fontWeight:500, color: done ? "#13BBAF" : active ? "var(--accent-ink)" : "var(--muted)", transition:"color 0.3s ease" }}>
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

type PageState = "loadingFixture" | "ready" | "generating" | "predicted" | "error" | "unavailable";

function PredictionContent({ matchId }: { matchId: string }) {
  const { user } = useAuth();
  const router = useRouter();

  const [fixture, setFixture] = useState<Fixture | null>(null);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [enriched, setEnriched] = useState<EnrichedData | null>(null);
  const [enrichedLoading, setEnrichedLoading] = useState(false);
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
    setEnriched(null);
    setEnrichedLoading(true);

    try {
      const token = await user.getIdToken(true);

      // Fire prediction and enriched fetch in parallel, don't wait for prediction before enriched
      const [predRes, enrichedRes] = await Promise.all([
        generatePrediction(matchId, token),
        (async () => {
          try {
            const freshToken = await user.getIdToken(true);
            return await fetch(
              `${API_BASE}/api/fixtures/${matchId}/enriched`,
              { headers: { Authorization: `Bearer ${freshToken}` } }
            );
          } catch {
            return null;
          }
        })(),
      ]);

      const raw = predRes.data as Record<string, unknown>;

      const pred: Prediction = {
        winner: (raw.winner as string) || "Unknown",
        confidence: (raw.confidence as string) || "low",
        reasoning: (raw.reasoning as string) || "",
        winProbability: (raw.winProbability as number) ?? (raw.win_probability as number) ?? undefined,
        home_win_probability: (raw.home_win_probability as number) ?? undefined,
        draw_probability: (raw.draw_probability as number) ?? undefined,
        away_win_probability: (raw.away_win_probability as number) ?? undefined,
        predictedScore: (raw.predictedScore as string) ?? (raw.predicted_score as string) ?? undefined,
        factors: (raw.factors as string[]) ?? undefined,
        riskFactors: (raw.riskFactors as string[]) ?? undefined,
        headToHead: raw.headToHead ? (raw.headToHead as Prediction["headToHead"]) : undefined,

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        keyFactors: (raw.keyFactors as any) ?? undefined,
        // Dixon-Coles three-way probabilities (not in Prediction type — accessed via cast)
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        homeWinProbability: (raw.home_win_probability as any) ?? undefined,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        drawProbability: (raw.draw_probability as any) ?? undefined,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        awayWinProbability: (raw.away_win_probability as any) ?? undefined,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        probabilityMethod: (raw.probability_method as any) ?? undefined,
      } as Prediction;

      setPrediction(pred);
      setPageState("predicted");

      // Handle enriched data if response available
      if (enrichedRes && enrichedRes.ok) {
        try {
          const enrichedJson = await enrichedRes.json();
          setEnriched(enrichedJson.data as EnrichedData);
        } catch {
          // Enriched data is optional
        }
      }

      setEnrichedLoading(false);
    } catch (err: unknown) {
      setEnrichedLoading(false);
      const msg = err instanceof Error ? err.message : "Prediction failed.";
      const detail = msg.replace(/^API \d+:\s*/, "");
      if (msg.includes("501")) {
        setErrorMsg("Prediction unavailable for this fixture — real football-data.org data required.");
        setPageState("unavailable");
      } else if (msg.includes("403") || msg.includes("429")) {
        // Access allowlist or daily prediction limit — show the backend's reason.
        setErrorMsg(detail);
        setPageState("unavailable");
      } else {
        setErrorMsg(detail);
        setPageState("error");
      }
    }
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const keyFactors = (prediction as any)?.keyFactors as Array<{ title: string; text: string }> | undefined;

  return (
    <div className="min-h-screen">
      <Navbar />

      <div className="relative pt-20">
        <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-48" style={{
          background: "radial-gradient(ellipse 60% 40% at 50% 0%, rgba(39,90,83,0.18) 0%, transparent 70%)",
        }} />
        <div className="relative mx-auto max-w-4xl px-4 pt-10 pb-4 sm:px-6">
          <Link href="/dashboard" className="mb-4 inline-flex items-center gap-1.5 text-sm transition-colors"
            style={{ color: "var(--muted)" }}
            onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = "var(--accent-2)")}
            onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = "var(--muted)")}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
            Back to matches
          </Link>
          {fixture && (
            <h1 className="text-2xl font-extrabold sm:text-3xl" style={{ color: "var(--ink)", fontFamily: "var(--font-display), system-ui", letterSpacing: "-0.02em" }}>
              {fixture.name}
            </h1>
          )}
        </div>
      </div>

      <div className="mx-auto max-w-4xl px-4 pb-16 sm:px-6 space-y-4">

        {pageState === "loadingFixture" && <PredictionSkeleton />}

        {pageState === "ready" && fixture && (
          <div className="space-y-4">
            <MatchHeaderCard fixture={fixture} />
            <div className="card-glass p-8 flex flex-col items-center text-center gap-5">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl"
                style={{ background: "linear-gradient(135deg, rgba(39,90,83,0.3), rgba(19,187,175,0.2))", border: "1px solid var(--accent-edge)" }}>
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" style={{ color: "var(--accent-2)" }}>
                  <path d="M13 10V3L4 14h7v7l9-11h-7z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <div>
                <h2 className="text-xl font-bold" style={{ color: "var(--ink)", fontFamily: "var(--font-display), system-ui" }}>Ready to predict</h2>
                <p className="mt-1.5 text-sm max-w-xs" style={{ color: "var(--muted)" }}>
                  Gemini AI will analyse head-to-head records, standings, xG data, injuries and recent form to generate a structured prediction.
                </p>
              </div>
              <button onClick={handlePredict} className="btn-primary text-base px-10 py-3.5">
                Generate AI Prediction
              </button>
            </div>
          </div>
        )}

        {pageState === "generating" && fixture && (
          <PredictLoadingState home={fixture.homeTeam.name} away={fixture.awayTeam.name} />
        )}

        {pageState === "predicted" && prediction && fixture && (
          <AnimatePresence>
            <motion.div
              className="space-y-4"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.3 }}
            >
              <MatchHeaderCard fixture={fixture} />
              <AIVerdictCard fixture={fixture} prediction={prediction} />

              {prediction.headToHead && (
                <H2HTimeline h2h={prediction.headToHead} teamA={fixture.homeTeam.name} teamB={fixture.awayTeam.name} />
              )}

              {enrichedLoading ? <SectionSkeleton height={160} /> : enriched ? (
                <RecentFormSection
                  formA={enriched.team_a_recent_form} formB={enriched.team_b_recent_form}
                  teamA={fixture.homeTeam.name} teamB={fixture.awayTeam.name}
                  teamAId={fixture.homeTeam.id} teamBId={fixture.awayTeam.id}
                />
              ) : null}

              {enrichedLoading ? <SectionSkeleton height={160} /> : enriched?.xg ? (
                <XGSection xg={enriched.xg} teamA={fixture.homeTeam.name} teamB={fixture.awayTeam.name} />
              ) : null}

              {enrichedLoading ? <SectionSkeleton height={130} /> : enriched ? (
                <InjurySection injuries={enriched.injuries} teamA={fixture.homeTeam.name} teamB={fixture.awayTeam.name} />
              ) : null}

              {enrichedLoading ? <SectionSkeleton height={200} /> : enriched ? (
                <SeasonStatsSection statsA={enriched.team_a_stats} statsB={enriched.team_b_stats} teamA={fixture.homeTeam.name} teamB={fixture.awayTeam.name} />
              ) : null}

              {enrichedLoading ? <SectionSkeleton height={220} /> : enriched?.standings ? (
                <StandingsSection standings={enriched.standings} teamAId={fixture.homeTeam.id} teamBId={fixture.awayTeam.id} />
              ) : null}

              {!enrichedLoading && enriched?.trends && (
                <TrendsSection trends={enriched.trends} teamA={fixture.homeTeam.name} teamB={fixture.awayTeam.name} />
              )}

              {prediction.reasoning && <ReasoningBreakdown reasoning={prediction.reasoning} />}
              {keyFactors && keyFactors.length > 0 && <KeyFactorsList keyFactors={keyFactors} />}

              <PredictionSummaryPanel fixture={fixture} prediction={prediction} />
              <DataAvailabilitySection />

              <div className="text-center pt-2">
                <button onClick={handlePredict} className="btn-ghost text-sm px-6 py-2.5">
                  Regenerate prediction
                </button>
              </div>

              <Disclaimer />
            </motion.div>
          </AnimatePresence>
        )}

        {pageState === "unavailable" && (
          <div className="card-glass p-8 flex flex-col items-center text-center gap-4" style={{ borderColor: "rgba(248,194,92,0.2)" }}>
            <div className="flex h-14 w-14 items-center justify-center rounded-full" style={{ background: "var(--warm-bg)", border: "1px solid rgba(248,194,92,0.2)" }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" style={{ color: "#F8C25C" }}>
                <path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div>
              <h3 className="font-semibold" style={{ color: "var(--ink)" }}>Prediction Unavailable</h3>
              <p className="mt-2 text-sm max-w-sm" style={{ color: "var(--muted)" }}>
                {errorMsg || "Backend endpoint pending — real football-data.org data required for this fixture."}
              </p>
            </div>
            <Link href="/dashboard" className="btn-ghost text-sm px-6 py-2.5">← Back to matches</Link>
          </div>
        )}

        {pageState === "error" && (
          <ErrorState
            title="Failed to load prediction"
            message={errorMsg}
            onRetry={() => {
              if (!prediction) { setPageState("loadingFixture"); router.refresh(); }
              else { handlePredict(); }
            }}
          />
        )}
      </div>
    </div>
  );
}

export default function PredictionPage({ params }: { params: { matchId: string } }) {
  return (
    <ProtectedRoute>
      <PredictionContent matchId={params.matchId} />
    </ProtectedRoute>
  );
}
