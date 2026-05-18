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

// ── Small shared components ───────────────────────────────────────────────────

function SectionBadge({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-blue-500/20 bg-blue-500/8 px-2 py-0.5 text-[9px] font-bold uppercase tracking-widest text-blue-400">
      <span className="h-1 w-1 rounded-full bg-blue-400" />
      {label}
    </span>
  );
}

function SectionSkeleton({ height = 120 }: { height?: number }) {
  return (
    <div
      className="card-glass animate-pulse rounded-2xl bg-white/4"
      style={{ height }}
    />
  );
}

function DataUnavailable() {
  return (
    <p className="text-xs text-gray-600 italic">Data temporarily unavailable</p>
  );
}

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

// ── Team logo helper ──────────────────────────────────────────────────────────

function TeamLogo({ src, name, size = 64 }: { src?: string | null; name: string; size?: number }) {
  const [failed, setFailed] = useState(false);
  if (src && !failed) {
    return (
      <img
        src={src}
        alt={name}
        width={size}
        height={size}
        className="object-contain"
        style={{ width: size, height: size }}
        onError={() => setFailed(true)}
      />
    );
  }
  return (
    <span
      className="flex items-center justify-center rounded-2xl bg-gradient-to-br from-purple-900/60 to-violet-900/40 border border-purple-500/25 font-black text-purple-200"
      style={{ width: size, height: size, fontSize: size * 0.4 }}
    >
      {name.charAt(0)}
    </span>
  );
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
          <div className="flex-1 text-center">
            <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center">
              <TeamLogo src={fixture.homeTeam.logo} name={fixture.homeTeam.name} size={64} />
            </div>
            <p className="font-bold text-white leading-tight">{fixture.homeTeam.name}</p>
            <p className="text-xs text-gray-500 mt-0.5">Home</p>
          </div>
          <div className="flex flex-col items-center gap-2">
            <span className="text-xs font-black text-gray-600 tracking-[0.2em]">VS</span>
            <div className="h-px w-12 bg-gradient-to-r from-transparent via-purple-500/50 to-transparent" />
          </div>
          <div className="flex-1 text-center">
            <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center">
              <TeamLogo src={fixture.awayTeam.logo} name={fixture.awayTeam.name} size={64} />
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
        <div className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-purple-500/30 bg-purple-500/10 px-3 py-1">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" className="text-purple-400">
            <path d="M13 10V3L4 14h7v7l9-11h-7z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span className="text-xs font-bold uppercase tracking-widest text-purple-300">
            AI Verdict
          </span>
        </div>
        <p className="text-sm text-gray-400 mb-1">{headline}</p>
        <h2 className="text-4xl font-extrabold text-white sm:text-5xl">{winner}</h2>
        <p className="mt-1.5 text-sm text-gray-500">predicted to win over {loser}</p>
        <div className="mt-4 flex items-center justify-center gap-2">
          <span className={confidenceBadgeClass(prediction.confidence)}>
            {prediction.confidence
              ? prediction.confidence.charAt(0).toUpperCase() + prediction.confidence.slice(1)
              : "Unknown"}{" "}
            Confidence
          </span>
        </div>
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
      </div>
    </div>
  );
}

// ── Section 2 — H2H Timeline ─────────────────────────────────────────────────

function H2HTimeline({
  h2h,
  teamA,
  teamB,
}: {
  h2h: Prediction["headToHead"];
  teamA: string;
  teamB: string;
}) {
  if (!h2h) return null;

  function resultBadge(result_info: string): { label: string; cls: string } {
    const ri = (result_info || "").toLowerCase();
    if (teamA.toLowerCase().split(" ").some((w) => ri.includes(w)) && ri.includes("won"))
      return { label: "W", cls: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" };
    if (teamB.toLowerCase().split(" ").some((w) => ri.includes(w)) && ri.includes("won"))
      return { label: "L", cls: "bg-red-500/20 text-red-400 border-red-500/30" };
    return { label: "D", cls: "bg-amber-500/20 text-amber-400 border-amber-500/30" };
  }

  function rowBorder(result_info: string) {
    const ri = (result_info || "").toLowerCase();
    if (teamA.toLowerCase().split(" ").some((w) => ri.includes(w)) && ri.includes("won"))
      return "border-l-emerald-500/50";
    if (teamB.toLowerCase().split(" ").some((w) => ri.includes(w)) && ri.includes("won"))
      return "border-l-red-500/50";
    return "border-l-amber-500/50";
  }

  return (
    <div className="card-glass p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="section-label">Head to Head History</h3>
        <SectionBadge label="HISTORICAL DATA • SportMonks v3" />
      </div>
      <div className="flex gap-6 mb-4 text-center">
        {[
          { val: h2h.teamAWins, label: teamA },
          { val: h2h.draws, label: "Draws" },
          { val: h2h.teamBWins, label: teamB },
        ].map(({ val, label }) => (
          <div key={label} className="stat-cell flex-1">
            <p className="text-2xl font-bold text-white">{val}</p>
            <p className="text-[11px] text-gray-500 mt-0.5 truncate">{label}</p>
          </div>
        ))}
      </div>
      {(h2h.recentResults || []).length > 0 && (
        <div className="space-y-2 mt-4">
          {(h2h.recentResults || []).map((r, i) => {
            const badge = resultBadge(r.result_info);
            return (
              <div
                key={i}
                className={`flex items-center gap-3 rounded-lg border-l-2 bg-white/3 px-3 py-2.5 text-xs ${rowBorder(r.result_info)}`}
              >
                <span className="text-gray-500 shrink-0 w-20">{r.date}</span>
                <span className="text-gray-300 flex-1 truncate">{r.name}</span>
                <span
                  className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold ${badge.cls}`}
                >
                  {badge.label}
                </span>
              </div>
            );
          })}
        </div>
      )}
      <p className="mt-3 text-right text-xs text-gray-600">{h2h.total} total matches</p>
    </div>
  );
}

// ── Section 3 — Recent Form with General | xG match cards ────────────────────

/** Split bar: left portion (home/purple) + right portion (away/blue) = 100% */
function SplitBar({
  homeVal, awayVal, redBars = false,
}: {
  homeVal: number | null; awayVal: number | null; redBars?: boolean;
}) {
  const h = homeVal ?? 0;
  const a = awayVal ?? 0;
  const total = h + a;
  const homeW = total > 0 ? (h / total) * 100 : 50;
  const awayW = total > 0 ? (a / total) * 100 : 50;
  const homeColor = redBars ? "#ef4444" : "#7c3aed";
  const awayColor = redBars ? "#ef4444" : "#3b82f6";
  return (
    <div className="flex w-full h-1.5 rounded-full overflow-hidden mt-1">
      <div style={{ width: `${homeW}%`, background: homeColor, transition: "width 0.4s ease" }} />
      <div style={{ width: `${awayW}%`, background: awayColor, transition: "width 0.4s ease" }} />
    </div>
  );
}

/** One stat row: homeValue  stat-name  awayValue + split bar below */
function StatRow({
  name, homeVal, awayVal, fmt = String, redBars = false,
}: {
  name: string;
  homeVal: number | null;
  awayVal: number | null;
  fmt?: (v: number) => string;
  redBars?: boolean;
}) {
  return (
    <div className="mb-3">
      <div className="flex items-baseline justify-between">
        <span className="text-sm text-gray-200 w-12 text-left font-medium">
          {homeVal != null ? fmt(homeVal) : "—"}
        </span>
        <span className="text-xs italic text-gray-400 flex-1 text-center">{name}</span>
        <span className="text-sm text-gray-200 w-12 text-right font-medium">
          {awayVal != null ? fmt(awayVal) : "—"}
        </span>
      </div>
      {(homeVal != null || awayVal != null) && (
        <SplitBar homeVal={homeVal} awayVal={awayVal} redBars={redBars} />
      )}
    </div>
  );
}

// myStats/oppStats always means: our tracked team on left, opponent on right
function GeneralStatsTab({
  myStats, oppStats,
}: {
  myStats: GeneralStats | null;
  oppStats: GeneralStats | null;
}) {
  if (!myStats && !oppStats) {
    return <p className="text-xs text-gray-600 italic py-2">Match stats not available</p>;
  }
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

function XGStatsTab({
  myStats, oppStats,
}: {
  myStats: XGStats | null;
  oppStats: XGStats | null;
}) {
  if (!myStats && !oppStats) {
    return (
      <p className="text-xs text-gray-600 italic py-4 text-center">
        xG data is not available on the current SportMonks Starter plan.
        Upgrade to Growth plan or higher to unlock Expected Goals data.
      </p>
    );
  }
  const dp2 = (v: number) => v.toFixed(2);
  return (
    <div className="pt-2">
      <StatRow name="Expected Goals (xG)"              homeVal={myStats?.xg   ?? null} awayVal={oppStats?.xg   ?? null} fmt={dp2} />
      <StatRow name="Expected Goals on Target (xGoT)"  homeVal={myStats?.xgot ?? null} awayVal={oppStats?.xgot ?? null} fmt={dp2} />
      <StatRow name="Expected Points (xPTS)"           homeVal={myStats?.xpts ?? null} awayVal={oppStats?.xpts ?? null} fmt={dp2} />
      <StatRow name="Expected Goals Penalties (xGP)"   homeVal={myStats?.xgp  ?? null} awayVal={oppStats?.xgp  ?? null} fmt={dp2} />
      <StatRow name="Expected Goals Free Kicks (xGFK)" homeVal={myStats?.xgfk ?? null} awayVal={oppStats?.xgfk ?? null} fmt={dp2} />
      <StatRow name="Expected Goals Corners (xGC)"     homeVal={myStats?.xgc  ?? null} awayVal={oppStats?.xgc  ?? null} fmt={dp2} />
    </div>
  );
}

function MatchCard({
  fixture, teamId, defaultExpanded,
}: {
  fixture: RecentFixture; teamId: number; defaultExpanded: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [tab, setTab] = useState<"general" | "xg">("general");

  // Determine which side is "our" team so we always render it on the left
  const isHome  = fixture.home_team.id === teamId;
  const myTeam  = isHome ? fixture.home_team  : fixture.away_team;
  const oppTeam = isHome ? fixture.away_team  : fixture.home_team;

  // Stats: our team always on the left bar, opponent always on the right
  const myGeneral  = isHome ? fixture.general_stats?.home : fixture.general_stats?.away;
  const oppGeneral = isHome ? fixture.general_stats?.away : fixture.general_stats?.home;
  const myXg       = isHome ? fixture.xg_stats?.home      : fixture.xg_stats?.away;
  const oppXg      = isHome ? fixture.xg_stats?.away      : fixture.xg_stats?.home;

  // Score from our perspective: my goals — opp goals
  const myScore  = isHome ? fixture.score?.home : fixture.score?.away;
  const oppScore = isHome ? fixture.score?.away : fixture.score?.home;
  const scoreStr =
    myScore != null && oppScore != null ? `${myScore} — ${oppScore}` : "vs";

  // W/D/L from our team's perspective
  const ri = (fixture.result_info || "").toLowerCase();
  let resultLabel: "W" | "D" | "L" = "L";
  let resultCls = "bg-red-500/20 text-red-400 border-red-500/30";
  if (myTeam.name.toLowerCase().split(" ").some((w) => ri.includes(w)) && ri.includes("won")) {
    resultLabel = "W"; resultCls = "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
  } else if (ri.includes("draw") || ri.includes("drew")) {
    resultLabel = "D"; resultCls = "bg-amber-500/20 text-amber-400 border-amber-500/30";
  }

  return (
    <div className="rounded-xl border border-purple-500/10 bg-white/3 overflow-hidden mb-2">
      {/* Collapsed header — our team left, opponent right */}
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center gap-2 px-4 py-3 text-left hover:bg-white/4 transition-colors"
      >
        <TeamLogo src={myTeam.logo}  name={myTeam.name}  size={24} />
        <span className="text-xs text-gray-300 flex-1 truncate">{myTeam.name}</span>
        <span className="text-sm font-bold text-white px-2 shrink-0">{scoreStr}</span>
        <span className="text-xs text-gray-300 flex-1 text-right truncate">{oppTeam.name}</span>
        <TeamLogo src={oppTeam.logo} name={oppTeam.name} size={24} />
        <span className={`ml-2 shrink-0 rounded-full border px-1.5 py-0.5 text-[9px] font-bold ${resultCls}`}>
          {resultLabel}
        </span>
        <span className="text-[10px] text-gray-600 ml-1 shrink-0">{fixture.date}</span>
        <svg
          width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" className={`ml-1 text-gray-600 transition-transform ${expanded ? "rotate-180" : ""}`}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {expanded && (
        <div className="px-4 pb-4">
          {/* Statistics header: our logo left, opponent logo right */}
          <div className="flex items-center justify-between py-2 mb-1 border-t border-white/6">
            <TeamLogo src={myTeam.logo}  name={myTeam.name}  size={32} />
            <span className="text-xs font-bold text-gray-300 tracking-wide">Statistics</span>
            <TeamLogo src={oppTeam.logo} name={oppTeam.name} size={32} />
          </div>

          {/* Tab toggle */}
          <div className="flex rounded-full border border-purple-500/20 bg-white/4 p-0.5 mb-4">
            {(["general", "xg"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`flex-1 rounded-full py-1 text-xs font-semibold transition-all ${
                  tab === t
                    ? "bg-[#1e1b4b] text-white shadow"
                    : "text-gray-500 hover:text-gray-300"
                }`}
              >
                {t === "general" ? "General" : "xG"}
              </button>
            ))}
          </div>

          {tab === "general" && (
            <GeneralStatsTab myStats={myGeneral ?? null} oppStats={oppGeneral ?? null} />
          )}
          {tab === "xg" && (
            <XGStatsTab myStats={myXg ?? null} oppStats={oppXg ?? null} />
          )}
        </div>
      )}
    </div>
  );
}

function RecentFormSection({
  formA, formB, teamA, teamB, teamAId, teamBId,
}: {
  formA: RecentFixture[] | null;
  formB: RecentFixture[] | null;
  teamA: string;
  teamB: string;
  teamAId: number;
  teamBId: number;
}) {
  return (
    <div className="card-glass p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="section-label">Recent Form</h3>
        <SectionBadge label="SCHEDULES & RESULTS • SportMonks v3" />
      </div>
      <div className="grid grid-cols-2 gap-4">
        {[
          { name: teamA, fixtures: formA, tid: teamAId },
          { name: teamB, fixtures: formB, tid: teamBId },
        ].map(({ name, fixtures, tid }) => (
          <div key={name}>
            <p className="text-xs font-semibold text-gray-400 mb-2 truncate">{name}</p>
            {fixtures && fixtures.length > 0 ? (
              fixtures.map((f, i) => (
                <MatchCard
                  key={f.fixture_id ?? i}
                  fixture={f}
                  teamId={tid}
                  defaultExpanded={i === 0}
                />
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

// ── Section 4 — xG Analysis ───────────────────────────────────────────────────

function XGSection({
  xg, teamA, teamB,
}: {
  xg: { team_a_xg: number; team_b_xg: number } | null;
  teamA: string;
  teamB: string;
}) {
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
        <SectionBadge label="EXPECTED GOALS (xG) • SportMonks v3" />
      </div>
      <p className="text-xs text-gray-500 mb-5">
        xG = Expected Goals — measures quality of chances regardless of scoreline.
        Higher xG = better chances created.
      </p>
      <div className="space-y-4">
        {[
          { name: teamA, xgVal: xg.team_a_xg, pct: pctA },
          { name: teamB, xgVal: xg.team_b_xg, pct: pctB },
        ].map(({ name, xgVal, pct }) => (
          <div key={name}>
            <div className="flex justify-between text-xs mb-1.5">
              <span className="text-gray-300 truncate max-w-[60%]">{name}</span>
              <span className="font-bold text-white">{xgVal.toFixed(2)} xG</span>
            </div>
            <div className="h-3 rounded-full bg-white/6 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-purple-600 to-violet-500 transition-all duration-700"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs text-purple-300">
        {leader} created {diff} more xG — created better scoring chances
      </p>
    </div>
  );
}

// ── Section 5 — Injuries & Suspensions ───────────────────────────────────────

function InjurySection({
  injuries, teamA, teamB,
}: {
  injuries: { team_a: InjuryPlayer[]; team_b: InjuryPlayer[] } | null;
  teamA: string;
  teamB: string;
}) {
  function InjuryList({ players, label }: { players: InjuryPlayer[]; label: string }) {
    return (
      <div>
        <p className="text-xs font-semibold text-gray-400 mb-2 truncate">{label}</p>
        {players.length === 0 ? (
          <p className="text-xs text-emerald-400">✅ Full squad available</p>
        ) : (
          <div className="space-y-1.5">
            {players.map((p, i) => {
              const isSusp = p.type?.toLowerCase().includes("suspend");
              return (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span>{isSusp ? "🟡" : "🔴"}</span>
                  <span className="text-gray-300 flex-1 truncate">{p.player_name}</span>
                  <span
                    className={`shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold uppercase ${
                      isSusp
                        ? "bg-amber-500/20 text-amber-400"
                        : "bg-red-500/20 text-red-400"
                    }`}
                  >
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
        <SectionBadge label="INJURIES & SUSPENSIONS • SportMonks v3" />
      </div>
      {!injuries ? (
        <DataUnavailable />
      ) : (
        <div className="grid grid-cols-2 gap-6">
          <InjuryList players={injuries.team_a} label={teamA} />
          <InjuryList players={injuries.team_b} label={teamB} />
        </div>
      )}
    </div>
  );
}

// ── Section 6 — Season Stats Comparison ──────────────────────────────────────

function StatBar({
  label, valA, valB, nameA, nameB, invert = false,
}: {
  label: string; valA: number | null; valB: number | null;
  nameA: string; nameB: string; invert?: boolean;
}) {
  const a = valA ?? 0;
  const b = valB ?? 0;
  const max = Math.max(a, b, 1);
  const pA = Math.round((a / max) * 100);
  const pB = Math.round((b / max) * 100);
  const barA = invert ? "from-red-700 to-red-600" : "from-purple-600 to-violet-500";
  const barB = invert ? "from-red-700 to-red-600" : "from-violet-600 to-purple-500";

  return (
    <div className="mb-4">
      <p className="text-xs text-gray-500 mb-1.5">{label}</p>
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-gray-400 truncate max-w-[60%]">{nameA}</span>
            <span className="font-bold text-white">{valA ?? "—"}</span>
          </div>
          <div className="h-2 rounded-full bg-white/6 overflow-hidden">
            <div
              className={`h-full rounded-full bg-gradient-to-r ${barA}`}
              style={{ width: `${pA}%` }}
            />
          </div>
        </div>
        <div className="flex-1">
          <div className="flex justify-between text-xs mb-1">
            <span className="font-bold text-white">{valB ?? "—"}</span>
            <span className="text-gray-400 truncate max-w-[60%] text-right">{nameB}</span>
          </div>
          <div className="h-2 rounded-full bg-white/6 overflow-hidden">
            <div
              className={`h-full rounded-full bg-gradient-to-r ${barB}`}
              style={{ width: `${pB}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function SeasonStatsSection({
  statsA, statsB, teamA, teamB,
}: {
  statsA: TeamStats | null;
  statsB: TeamStats | null;
  teamA: string;
  teamB: string;
}) {
  const noData = !statsA && !statsB;
  const totalA = statsA?.total_matches || 1;
  const totalB = statsB?.total_matches || 1;
  const wrA = statsA?.wins != null ? Math.round((statsA.wins / totalA) * 100) : null;
  const wrB = statsB?.wins != null ? Math.round((statsB.wins / totalB) * 100) : null;

  return (
    <div className="card-glass p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="section-label">Season Statistics</h3>
        <SectionBadge label="STATISTICS • SportMonks v3" />
      </div>
      {noData ? (
        <DataUnavailable />
      ) : (
        <>
          <StatBar label="Goals Scored" valA={statsA?.goals_scored ?? null} valB={statsB?.goals_scored ?? null} nameA={teamA} nameB={teamB} />
          <StatBar label="Goals Conceded" valA={statsA?.goals_conceded ?? null} valB={statsB?.goals_conceded ?? null} nameA={teamA} nameB={teamB} invert />
          <StatBar label="Clean Sheets" valA={statsA?.clean_sheets ?? null} valB={statsB?.clean_sheets ?? null} nameA={teamA} nameB={teamB} />
          <StatBar label="Win Rate (%)" valA={wrA} valB={wrB} nameA={teamA} nameB={teamB} />
        </>
      )}
    </div>
  );
}

// ── Section 7 — League Standings ─────────────────────────────────────────────

function StandingsSection({
  standings, teamAId, teamBId,
}: {
  standings: StandingRow[] | null;
  teamAId: number;
  teamBId: number;
}) {
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
        <SectionBadge label="STANDINGS • SportMonks v3" />
      </div>
      <table className="w-full text-xs text-gray-400">
        <thead>
          <tr className="border-b border-white/6">
            {["#", "Team", "P", "W", "D", "L", "GD", "Pts"].map((h) => (
              <th key={h} className={`pb-2 font-semibold text-gray-600 ${h === "Team" ? "text-left pl-2" : "text-center"}`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {slice.map((row) => {
            const isHighlighted =
              row.participant_id === teamAId || row.participant_id === teamBId;
            return (
              <tr
                key={row.participant_id}
                className={`border-l-2 transition-colors ${
                  isHighlighted
                    ? "border-l-purple-500 bg-purple-500/8"
                    : "border-l-transparent"
                }`}
              >
                <td className="py-2 text-center font-mono">{row.position}</td>
                <td className="py-2 pl-2 text-left">
                  <span className={isHighlighted ? "text-white font-semibold" : ""}>
                    {row.team_name || "—"}
                  </span>
                </td>
                {[
                  (row.won ?? 0) + (row.drawn ?? 0) + (row.lost ?? 0),
                  row.won,
                  row.drawn,
                  row.lost,
                  row.goal_difference,
                  row.points,
                ].map((val, i) => (
                  <td key={i} className="py-2 text-center font-mono">
                    {val ?? "—"}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── Section 8 — Trends ────────────────────────────────────────────────────────

const TREND_EMOJI: Record<string, string> = {
  scoring: "🔥", score: "🔥", goal: "⚽",
  clean: "🧱", unbeaten: "📈", btts: "⚽",
  win: "🏆", form: "📊",
};

function trendEmoji(label: string): string {
  const lower = label.toLowerCase();
  for (const [key, emoji] of Object.entries(TREND_EMOJI)) {
    if (lower.includes(key)) return emoji;
  }
  return "📌";
}

function TrendsSection({
  trends, teamA, teamB,
}: {
  trends: { team_a: string[]; team_b: string[] } | null;
  teamA: string;
  teamB: string;
}) {
  const hasAny =
    (trends?.team_a?.length ?? 0) > 0 || (trends?.team_b?.length ?? 0) > 0;
  if (!trends || !hasAny) return null;

  return (
    <div className="card-glass p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="section-label">Current Trends</h3>
        <SectionBadge label="LIVESCORES & EVENTS • SportMonks v3" />
      </div>
      <div className="grid grid-cols-2 gap-6">
        {[
          { name: teamA, items: trends.team_a },
          { name: teamB, items: trends.team_b },
        ].map(({ name, items }) => (
          <div key={name}>
            <p className="text-xs font-semibold text-gray-400 mb-2 truncate">{name}</p>
            {items.length === 0 ? (
              <p className="text-xs text-gray-600">No trend data</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {items.map((t, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 rounded-full border border-purple-500/20 bg-purple-500/10 px-2.5 py-1 text-xs text-purple-200"
                  >
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

// ── Existing supplementary sections ──────────────────────────────────────────

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

function KeyFactorsList({ keyFactors }: { keyFactors: Array<{ title: string; text: string }> }) {
  if (!keyFactors || keyFactors.length === 0) return null;
  return (
    <div className="card-glass p-6">
      <h3 className="section-label mb-4">Key Factors</h3>
      <div className="space-y-3">
        {keyFactors.map((kf, i) => (
          <div key={i} className="flex items-start gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-purple-500/20 border border-purple-500/30 text-[10px] font-bold text-purple-400">
              {i + 1}
            </span>
            <div>
              <p className="text-xs font-semibold text-purple-300 mb-0.5">{kf.title}</p>
              <p className="text-sm text-gray-300 leading-relaxed">{kf.text}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PredictionSummaryPanel({
  fixture, prediction,
}: {
  fixture: Fixture; prediction: Prediction;
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
              stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            />
          </svg>
        </div>
        <div>
          <h4 className="font-semibold text-white text-sm mb-1">Advanced Stats</h4>
          <p className="text-xs text-gray-500 leading-relaxed">
            xG, form tables, standings, injuries, and top scorers are sourced live from
            SportMonks v3. Player stats and predicted line-ups pending backend expansion.
          </p>
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
    <div style={{ display:"flex", flexDirection:"column", alignItems:"center", textAlign:"center", padding:"56px 24px", animation:"fadeUp 0.4s cubic-bezier(0.16,1,0.3,1)" }}>
      <div className="loading-orb" style={{ marginBottom: 36 }}>
        <div className="loading-orb-inner">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="currentColor" style={{ color:"var(--accent-2)" }}>
            <path d="M12 2 14 9l7 2-7 2-2 7-2-7-7-2 7-2 2-7Z" />
          </svg>
        </div>
      </div>
      <h3 style={{ fontSize:22, fontWeight:600, letterSpacing:"-0.02em", color:"var(--ink)", marginBottom:8 }}>
        Analysing {home} vs {away}
      </h3>
      <p style={{ fontSize:14, color:"var(--muted)", marginBottom:36, maxWidth:400 }}>
        Gemini AI is processing head-to-head records, standings, xG data and recent form.
        This may take 20–40 seconds.
      </p>
      <div style={{ display:"flex", flexDirection:"column", gap:10, width:"100%", maxWidth:360 }}>
        {STEPS.map((label, i) => {
          const done = i < step;
          const active = i === step;
          return (
            <div key={label} style={{ display:"flex", alignItems:"center", gap:12, padding:"11px 16px", borderRadius:12, background:done?"rgba(52,211,153,0.08)":active?"var(--accent-soft)":"var(--surface)", border:`1px solid ${done?"rgba(52,211,153,0.2)":active?"var(--accent-edge)":"var(--border)"}`, transition:"all 0.35s ease" }}>
              <div style={{ width:22, height:22, borderRadius:"50%", flexShrink:0, display:"grid", placeItems:"center", background:done?"#34D399":active?"var(--accent)":"var(--surface-2)", transition:"background 0.3s ease" }}>
                {done ? (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
                ) : active ? (
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="white" style={{ animation:"orbSpin 0.8s linear infinite" }}><path d="M12 2 14 9l7 2-7 2-2 7-2-7-7-2 7-2 2-7Z" /></svg>
                ) : (
                  <span style={{ width:6, height:6, borderRadius:"50%", background:"var(--border-s)" }} />
                )}
              </div>
              <span style={{ fontSize:13, fontWeight:500, color:done?"#34D399":active?"var(--accent-ink)":"var(--muted)", transition:"color 0.3s ease" }}>{label}</span>
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

    try {
      const token = await user.getIdToken(true);
      const res = await generatePrediction(matchId, token);
      const raw = res.data as Record<string, unknown>;

      const pred: Prediction = {
        winner: (raw.winner as string) || "Unknown",
        confidence: (raw.confidence as string) || "low",
        reasoning: (raw.reasoning as string) || "",
        winProbability: (raw.winProbability as number) ?? (raw.win_probability as number) ?? undefined,
        predictedScore: (raw.predictedScore as string) ?? (raw.predicted_score as string) ?? undefined,
        factors: (raw.factors as string[]) ?? undefined,
        riskFactors: (raw.riskFactors as string[]) ?? undefined,
        headToHead: raw.headToHead ? (raw.headToHead as Prediction["headToHead"]) : undefined,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        keyFactors: (raw.keyFactors as any) ?? undefined,
      };

      setPrediction(pred);
      setPageState("predicted");

      // Fetch enriched data after prediction displays — non-blocking
      setEnrichedLoading(true);
      try {
        const freshToken = await user.getIdToken(true);
        const enrichedRes = await fetch(
          `${API_BASE}/api/fixtures/${matchId}/enriched`,
          { headers: { Authorization: `Bearer ${freshToken}` } }
        );
        if (enrichedRes.ok) {
          const enrichedJson = await enrichedRes.json();
          setEnriched(enrichedJson.data as EnrichedData);
        }
      } catch {
        // Enriched data is optional — prediction still shows
      } finally {
        setEnrichedLoading(false);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Prediction failed.";
      if (msg.includes("501")) {
        setErrorMsg("Prediction unavailable for this fixture — real SportMonks data required.");
        setPageState("unavailable");
      } else {
        setErrorMsg(msg);
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
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-48"
          style={{ background:"radial-gradient(ellipse 60% 40% at 50% 0%, rgba(124,58,237,0.12) 0%, transparent 70%)" }}
        />

        <div className="relative mx-auto max-w-4xl px-4 pt-10 pb-4 sm:px-6">
          <Link href="/dashboard" className="mb-4 inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-purple-400 transition-colors">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
            Back to matches
          </Link>
          {fixture && <h1 className="text-2xl font-extrabold text-white sm:text-3xl">{fixture.name}</h1>}
        </div>
      </div>

      <div className="mx-auto max-w-4xl px-4 pb-16 sm:px-6 space-y-4">

        {/* Loading fixture */}
        {pageState === "loadingFixture" && <PredictionSkeleton />}

        {/* Ready state */}
        {pageState === "ready" && fixture && (
          <div className="space-y-4">
            <MatchHeaderCard fixture={fixture} />
            <div className="card-glass p-8 flex flex-col items-center text-center gap-5">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-600/20 to-purple-600/20 border border-purple-500/30">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" className="text-purple-400">
                  <path d="M13 10V3L4 14h7v7l9-11h-7z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <div>
                <h2 className="text-xl font-bold text-white">Ready to predict</h2>
                <p className="mt-1.5 text-sm text-gray-500 max-w-xs">
                  Gemini AI will analyse head-to-head records, standings, xG data, injuries and recent form to generate a structured prediction.
                </p>
              </div>
              <button onClick={handlePredict} className="btn-primary text-base px-10 py-3.5">
                Generate AI Prediction
              </button>
            </div>
          </div>
        )}

        {/* Generating */}
        {pageState === "generating" && fixture && (
          <PredictLoadingState home={fixture.homeTeam.name} away={fixture.awayTeam.name} />
        )}

        {/* Prediction result */}
        {pageState === "predicted" && prediction && fixture && (
          <div className="space-y-4 animate-fade-in">

            {/* 1. Match header with logos */}
            <MatchHeaderCard fixture={fixture} />

            {/* AI Verdict — shows immediately */}
            <AIVerdictCard fixture={fixture} prediction={prediction} />

            {/* 2. H2H History — from prediction response */}
            {prediction.headToHead && (
              <H2HTimeline
                h2h={prediction.headToHead}
                teamA={fixture.homeTeam.name}
                teamB={fixture.awayTeam.name}
              />
            )}

            {/* 3. Recent Form — from enriched */}
            {enrichedLoading ? (
              <SectionSkeleton height={160} />
            ) : enriched ? (
              <RecentFormSection
                formA={enriched.team_a_recent_form}
                formB={enriched.team_b_recent_form}
                teamA={fixture.homeTeam.name}
                teamB={fixture.awayTeam.name}
                teamAId={fixture.homeTeam.id}
                teamBId={fixture.awayTeam.id}
              />
            ) : null}

            {/* 4. xG Analysis — from enriched */}
            {enrichedLoading ? (
              <SectionSkeleton height={160} />
            ) : enriched?.xg ? (
              <XGSection
                xg={enriched.xg}
                teamA={fixture.homeTeam.name}
                teamB={fixture.awayTeam.name}
              />
            ) : null}

            {/* 5. Injuries & Suspensions — from enriched */}
            {enrichedLoading ? (
              <SectionSkeleton height={130} />
            ) : enriched ? (
              <InjurySection
                injuries={enriched.injuries}
                teamA={fixture.homeTeam.name}
                teamB={fixture.awayTeam.name}
              />
            ) : null}

            {/* 6. Season Statistics — from enriched */}
            {enrichedLoading ? (
              <SectionSkeleton height={200} />
            ) : enriched ? (
              <SeasonStatsSection
                statsA={enriched.team_a_stats}
                statsB={enriched.team_b_stats}
                teamA={fixture.homeTeam.name}
                teamB={fixture.awayTeam.name}
              />
            ) : null}

            {/* 7. League Standings — from enriched */}
            {enrichedLoading ? (
              <SectionSkeleton height={220} />
            ) : enriched?.standings ? (
              <StandingsSection
                standings={enriched.standings}
                teamAId={fixture.homeTeam.id}
                teamBId={fixture.awayTeam.id}
              />
            ) : null}

            {/* 8. Trends — hidden when empty */}
            {!enrichedLoading && enriched?.trends && (
              <TrendsSection
                trends={enriched.trends}
                teamA={fixture.homeTeam.name}
                teamB={fixture.awayTeam.name}
              />
            )}

            {/* Reasoning breakdown */}
            {prediction.reasoning && (
              <ReasoningBreakdown reasoning={prediction.reasoning} />
            )}

            {/* Key factors from Gemini */}
            {keyFactors && keyFactors.length > 0 && (
              <KeyFactorsList keyFactors={keyFactors} />
            )}

            {/* Prediction summary */}
            <PredictionSummaryPanel fixture={fixture} prediction={prediction} />

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
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-amber-400">
                <path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div>
              <h3 className="font-semibold text-white">Prediction Unavailable</h3>
              <p className="mt-2 text-sm text-gray-500 max-w-sm">
                {errorMsg || "Backend endpoint pending — real SportMonks data required for this fixture."}
              </p>
            </div>
            <Link href="/dashboard" className="btn-ghost text-sm px-6 py-2.5">← Back to matches</Link>
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
