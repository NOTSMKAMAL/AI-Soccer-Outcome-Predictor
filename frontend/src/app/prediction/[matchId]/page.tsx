"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence, MotionConfig, useReducedMotion } from "framer-motion";
import ProtectedRoute from "@/components/ProtectedRoute";
import Navbar from "@/components/Navbar";
import { PredictionSkeleton } from "@/components/LoadingSkeleton";
import ErrorState from "@/components/ErrorState";
import AllowanceBadge from "@/components/AllowanceBadge";
import TeamBadge from "@/components/TeamBadge";
import VerifyEmailNotice from "@/components/VerifyEmailNotice";
import { describeApiError, getFixtureById, generatePrediction, getPredictionAllowance } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import type { Fixture, Prediction, PredictionAllowance } from "@/lib/types";
import { resultFromScores, type MatchResult } from "@/lib/matchResult";
import { extractInsightChips } from "@/lib/reasoningInsights";

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
  home_team: { id: number | null; name: string };
  away_team: { id: number | null; name: string };
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

interface EnrichedData {
  team_a_recent_form: RecentFixture[] | null;
  team_b_recent_form: RecentFixture[] | null;
  standings: StandingRow[] | null;
  team_a_stats: TeamStats | null;
  team_b_stats: TeamStats | null;
  xg: { team_a_xg: number; team_b_xg: number } | null;
  trends: { team_a: string[]; team_b: string[] } | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ── Shared micro-components ───────────────────────────────────────────────────

function SectionBadge({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-bold uppercase tracking-widest"
      style={{ borderColor: "var(--primary-edge)", background: "var(--primary-soft)", color: "var(--primary-text)" }}>
      <span className="h-1 w-1 rounded-full" style={{ background: "var(--primary-text)" }} />
      {label}
    </span>
  );
}

function SectionSkeleton({ height = 120 }: { height?: number }) {
  return <div className="card animate-pulse rounded-2xl" style={{ height }} />;
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
  if (winner.toLowerCase() === "draw") return "The most likely result";
  const c = confidence?.toLowerCase();
  if (c === "high") return `${winner} looks like the clear favourite`;
  if (c === "medium") return `${winner} has the edge`;
  return `${winner} slightly ahead — a tight call`;
}

// ── Three-segment probability bar ─────────────────────────────────────────────

function ThreeSegmentBar({
  homeP, drawP, awayP, homeName, awayName,
}: {
  homeP: number; drawP: number; awayP: number; homeName: string; awayName: string;
}) {
  const reduceMotion = useReducedMotion();
  const total = homeP + drawP + awayP || 100;
  const hW = (homeP / total) * 100;
  const dW = (drawP / total) * 100;
  const aW = (awayP / total) * 100;

  return (
    <div className="mt-6 mx-auto w-full max-w-xs space-y-2">
      {/* Labels */}
      <div className="grid grid-cols-3 text-center text-xs" style={{ color: "var(--muted)" }}>
        <span className="break-words px-1 text-left">{homeName}</span>
        <span>Draw</span>
        <span className="break-words px-1 text-right">{awayName}</span>
      </div>

      {/* Bar */}
      <div className="h-3 rounded-full overflow-hidden flex gap-0.5" style={{ background: "var(--surface-2)" }}>
        <motion.div
          initial={reduceMotion ? false : { width: 0 }}
          animate={{ width: `${hW}%` }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1], delay: 0.15 }}
          style={{
            height: "100%", minWidth: hW > 0 ? 6 : 0,
            background: "var(--home)",
            borderRadius: "999px 2px 2px 999px",
          }}
        />
        <motion.div
          initial={reduceMotion ? false : { width: 0 }}
          animate={{ width: `${dW}%` }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1], delay: 0.3 }}
          style={{
            height: "100%", minWidth: dW > 0 ? 6 : 0,
            background: "var(--draw)",
          }}
        />
        <motion.div
          initial={reduceMotion ? false : { width: 0 }}
          animate={{ width: `${aW}%` }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1], delay: 0.45 }}
          style={{
            height: "100%", minWidth: aW > 0 ? 6 : 0,
            background: "var(--away)",
            borderRadius: "2px 999px 999px 2px",
          }}
        />
      </div>

      {/* Percentages */}
      <div className="grid grid-cols-3 text-center font-bold text-sm"
        style={{ fontFamily: "var(--font-display), system-ui" }}>
        <span style={{ color: "var(--home-text)" }}>{(homeP * 100).toFixed(0)}%</span>
        <span style={{ color: "var(--muted)" }}>{(drawP * 100).toFixed(0)}%</span>
        <span style={{ color: "var(--away)" }}>{(awayP * 100).toFixed(0)}%</span>
      </div>
    </div>
  );
}

// ── MatchHeaderCard ───────────────────────────────────────────────────────────

function MatchHeaderCard({ fixture }: { fixture: Fixture }) {
  return (
    <div className="card p-6 relative overflow-hidden">
      <div className="relative z-10">
        {/* Badges */}
        <div className="mb-5 flex flex-wrap items-center gap-2">
          <span className="badge-football-data flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: "var(--primary-text)" }} />
            football-data.org
          </span>
          <span className="badge-gemini flex items-center gap-1.5">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none">
              <path d="M13 10V3L4 14h7v7l9-11h-7z" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Gemini AI
          </span>
          {fixture._isMock && <span className="badge-preview">Preview data</span>}
          <span className="ml-auto text-xs rounded-full px-2.5 py-0.5" style={{ color: "var(--muted)", background: "var(--neutral-soft)", border: "1px solid var(--neutral-edge)" }}>
            {fixture.leagueName}
          </span>
        </div>

        {/* Teams VS */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1 text-center">
            <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center">
              <TeamBadge name={fixture.homeTeam.name} size={64} />
            </div>
            <p className="font-bold leading-tight" style={{ color: "var(--ink)" }}>{fixture.homeTeam.name}</p>
            <p className="text-xs mt-0.5" style={{ color: "var(--muted-2)" }}>Home</p>
          </div>
          <div className="flex flex-col items-center gap-2">
            <span className="text-xs font-black tracking-[0.2em]" style={{ color: "var(--muted-2)" }}>VS</span>
            <div className="h-px w-12" style={{ background: "var(--border-s)" }} />
          </div>
          <div className="flex-1 text-center">
            <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center">
              <TeamBadge name={fixture.awayTeam.name} size={64} />
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

  // Three-segment bar data
  const hasThreeProbs =
    prediction.home_win_probability != null &&
    prediction.draw_probability != null &&
    prediction.away_win_probability != null;

  const homeP = prediction.home_win_probability ?? 0;
  const drawP = prediction.draw_probability ?? 0;
  const awayP = prediction.away_win_probability ?? 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="card p-6 text-center relative overflow-hidden"
    >
      <div className="sig-rule" style={{ position: "absolute", inset: "0 0 auto 0" }} />

      <div className="relative z-10">
        {/* AI Verdict badge */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.1, duration: 0.4 }}
          className="mb-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1"
          style={{ border: "1px solid var(--primary-edge)", background: "var(--primary-soft)" }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" style={{ color: "var(--primary-text)" }}>
            <path d="M13 10V3L4 14h7v7l9-11h-7z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span className="text-xs font-bold uppercase tracking-widest" style={{ color: "var(--primary-text)" }}>
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

        <p className="mt-1.5 text-sm" style={{ color: "var(--muted-2)" }}>
          {winner.toLowerCase() === "draw"
            ? `between ${fixture.homeTeam.name} and ${fixture.awayTeam.name}`
            : `predicted to win over ${loser}`}
        </p>

        <div className="mt-4 flex items-center justify-center gap-2">
          <span className={confidenceBadgeClass(prediction.confidence)}>
            {prediction.confidence
              ? prediction.confidence.charAt(0).toUpperCase() + prediction.confidence.slice(1)
              : "Unknown"}{" "}
            Confidence
          </span>
        </div>

        {/* ── Three-segment bar (primary) — uses actual Dixon-Coles probabilities ── */}
        {hasThreeProbs && (
          <ThreeSegmentBar
            homeP={homeP}
            drawP={drawP}
            awayP={awayP}
            homeName={fixture.homeTeam.name}
            awayName={fixture.awayTeam.name}
          />
        )}

        {prediction.probabilityMethod === "confidence-estimate" && (
          <p className="mt-3 mx-auto max-w-xs text-xs" style={{ color: "var(--muted)" }}>
            League standings weren&apos;t available, so these are rough estimates from Gemini&apos;s confidence, not the model&apos;s probabilities.
          </p>
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
      return { label: "W", cls: "result-W" };
    if (teamB.toLowerCase().split(" ").some((w) => ri.includes(w)) && ri.includes("won"))
      return { label: "L", cls: "result-L" };
    return { label: "D", cls: "result-D" };
  }

  function rowBorder(result_info: string) {
    const ri = (result_info || "").toLowerCase();
    if (teamA.toLowerCase().split(" ").some((w) => ri.includes(w)) && ri.includes("won"))
      return "[border-left-color:var(--primary)]";
    if (teamB.toLowerCase().split(" ").some((w) => ri.includes(w)) && ri.includes("won"))
      return "[border-left-color:var(--orange)]";
    return "[border-left-color:var(--neutral)]";
  }

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="section-label">Head to Head History</h3>
        <SectionBadge label="HISTORICAL DATA • football-data.org" />
      </div>
      <div className="grid grid-cols-3 gap-2 mb-4 text-center">
        {[
          { val: h2h.teamAWins, label: teamA },
          { val: h2h.draws, label: "Draws" },
          { val: h2h.teamBWins, label: teamB },
        ].map(({ val, label }) => (
          <div key={label} className="stat-cell min-w-0" style={{ padding: "12px 8px" }}>
            <p className="text-2xl font-bold" style={{ color: "var(--ink)", fontFamily: "var(--font-display), system-ui" }}>{val}</p>
            <p className="text-xs mt-0.5 break-words" style={{ color: "var(--muted)" }}>{label}</p>
          </div>
        ))}
      </div>
      {(h2h.recentResults || []).length > 0 && (
        <div className="space-y-2 mt-4">
          {(h2h.recentResults || []).map((r, i) => {
            const badge = resultBadge(r.result_info);
            return (
              <div key={i} className={`flex items-center gap-3 rounded-lg border-l-2 px-3 py-2.5 text-xs ${rowBorder(r.result_info)}`}
                style={{ background: "var(--surface-2)" }}>
                <span className="shrink-0 w-20" style={{ color: "var(--muted)" }}>{r.date}</span>
                <span className="flex-1 min-w-0" style={{ color: "var(--ink-2)" }}>{r.name}</span>
                <span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-bold ${badge.cls}`}>
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

function SplitBar({ homeVal, awayVal }: { homeVal: number | null; awayVal: number | null }) {
  const h = homeVal ?? 0;
  const a = awayVal ?? 0;
  const total = h + a;
  const homeW = total > 0 ? (h / total) * 100 : 50;
  const awayW = total > 0 ? (a / total) * 100 : 50;
  return (
    <div className="flex w-full h-1.5 rounded-full overflow-hidden mt-1">
      <div style={{ width: `${homeW}%`, background: "var(--home)", transition: "width 0.4s ease" }} />
      <div style={{ width: `${awayW}%`, background: "var(--away)", transition: "width 0.4s ease" }} />
    </div>
  );
}

function StatRow({ name, homeVal, awayVal, fmt = String }: {
  name: string; homeVal: number | null; awayVal: number | null;
  fmt?: (v: number) => string;
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
        <SplitBar homeVal={homeVal} awayVal={awayVal} />
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
      <StatRow name="Yellow Cards"    homeVal={myStats?.yellow_cards ?? null}    awayVal={oppStats?.yellow_cards ?? null} />
    </div>
  );
}

const RESULT_BADGE_CLS: Record<MatchResult, string> = {
  W: "result-W",
  D: "result-D",
  L: "result-L",
};

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
  const resultLabel = resultFromScores(myScore, oppScore);
  const resultCls = resultLabel ? RESULT_BADGE_CLS[resultLabel] : "";

  return (
    <div className="rounded-xl overflow-hidden mb-2" style={{ border: "1px solid var(--border)", background: "var(--surface-2)" }}>
      <button
        onClick={() => setExpanded((e) => !e)}
        className="hover-fill-strong w-full flex flex-wrap items-center gap-2 px-4 py-3 text-left transition-colors"
        style={{ cursor: "pointer" }}
      >
        <TeamBadge name={myTeam.name} size={32} />
        <span className="text-xs flex-1 min-w-0 break-words" style={{ color: "var(--ink-2)" }}>{myTeam.name}</span>
        <span className="text-sm font-bold px-2 shrink-0" style={{ color: "var(--ink)" }}>{scoreStr}</span>
        <span className="text-xs flex-1 min-w-0 text-right break-words" style={{ color: "var(--ink-2)" }}>{oppTeam.name}</span>
        <TeamBadge name={oppTeam.name} size={32} />
        <span className="w-full flex items-center gap-2">
          {resultLabel && (
            <span className={`shrink-0 rounded-full border px-1.5 py-0.5 text-xs font-bold ${resultCls}`}>{resultLabel}</span>
          )}
          <span className="text-xs" style={{ color: "var(--muted-2)" }}>{fixture.date}</span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            className={`ml-auto transition-transform ${expanded ? "rotate-180" : ""}`} style={{ color: "var(--muted-2)" }}>
            <path d="M6 9l6 6 6-6" />
          </svg>
        </span>
      </button>
      {expanded && (
        <div className="px-4 pb-4">
          <div className="flex items-center justify-between py-2 mb-1" style={{ borderTop: "1px solid var(--border)" }}>
            <TeamBadge name={myTeam.name} size={32} />
            <span className="text-xs font-bold tracking-wide" style={{ color: "var(--ink-2)" }}>Statistics</span>
            <TeamBadge name={oppTeam.name} size={32} />
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
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="section-label">Recent Form</h3>
        <SectionBadge label="SCHEDULES & RESULTS • football-data.org" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {[
          { name: teamA, fixtures: formA, tid: teamAId },
          { name: teamB, fixtures: formB, tid: teamBId },
        ].map(({ name, fixtures, tid }) => (
          <div key={name}>
            <p className="text-xs font-semibold mb-2 break-words" style={{ color: "var(--muted)" }}>{name}</p>
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
  const reduceMotion = useReducedMotion();

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="section-label">xG Match Analysis</h3>
        <SectionBadge label="EXPECTED GOALS (xG) • football-data.org" />
      </div>
      <p className="text-xs mb-5" style={{ color: "var(--muted)" }}>
        xG = Expected Goals — measures quality of chances regardless of scoreline.
      </p>
      <div className="space-y-4">
        {[
          { name: teamA, xgVal: xg.team_a_xg, pct: pctA, color: "var(--home)" },
          { name: teamB, xgVal: xg.team_b_xg, pct: pctB, color: "var(--away)" },
        ].map(({ name, xgVal, pct, color }) => (
          <div key={name}>
            <div className="flex justify-between text-xs mb-1.5">
              <span className="break-words max-w-[60%]" style={{ color: "var(--ink-2)" }}>{name}</span>
              <span className="font-bold" style={{ color: "var(--ink)", fontFamily: "var(--font-display), system-ui" }}>{xgVal.toFixed(2)} xG</span>
            </div>
            <div className="h-3 rounded-full overflow-hidden" style={{ background: "var(--surface-2)" }}>
              <motion.div
                initial={reduceMotion ? false : { width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                className="h-full rounded-full"
                style={{ background: color }}
              />
            </div>
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs" style={{ color: "var(--primary-text)" }}>
        {leader} created {diff} more xG — created better scoring chances
      </p>
    </div>
  );
}

// ── Season Stats ──────────────────────────────────────────────────────────────

function StatBar({ label, valA, valB, nameA, nameB }: {
  label: string; valA: number | null; valB: number | null;
  nameA: string; nameB: string;
}) {
  const a = valA ?? 0;
  const b = valB ?? 0;
  const max = Math.max(a, b, 1);
  const pA = Math.round((a / max) * 100);
  const pB = Math.round((b / max) * 100);

  return (
    <div className="mb-4">
      <p className="text-xs mb-1.5" style={{ color: "var(--muted)" }}>{label}</p>
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <div className="flex justify-between text-xs mb-1">
            <span className="break-words max-w-[60%]" style={{ color: "var(--muted)" }}>{nameA}</span>
            <span className="font-bold" style={{ color: "var(--ink)" }}>{valA ?? "—"}</span>
          </div>
          <div className="h-2 rounded-full overflow-hidden" style={{ background: "var(--surface-2)" }}>
            <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${pA}%`, background: "var(--home)" }} />
          </div>
        </div>
        <div className="flex-1">
          <div className="flex justify-between text-xs mb-1">
            <span className="font-bold" style={{ color: "var(--ink)" }}>{valB ?? "—"}</span>
            <span className="break-words max-w-[60%] text-right" style={{ color: "var(--muted)" }}>{nameB}</span>
          </div>
          <div className="h-2 rounded-full overflow-hidden" style={{ background: "var(--surface-2)" }}>
            <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${pB}%`, background: "var(--away)" }} />
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
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="section-label">Season Statistics</h3>
        <SectionBadge label="STATISTICS • football-data.org" />
      </div>
      {noData ? <DataUnavailable /> : (
        <>
          <StatBar label="Goals Scored"   valA={statsA?.goals_scored ?? null}   valB={statsB?.goals_scored ?? null}   nameA={teamA} nameB={teamB} />
          <StatBar label="Goals Conceded" valA={statsA?.goals_conceded ?? null} valB={statsB?.goals_conceded ?? null} nameA={teamA} nameB={teamB} />
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
    <div className="card p-6 overflow-x-auto">
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
                className={`border-l-2 transition-colors ${isHighlighted ? "[border-left-color:var(--primary)]" : "border-l-transparent"}`}
                style={{ background: isHighlighted ? "var(--primary-soft)" : "transparent" }}
              >
                <td className="py-2 text-center font-mono">{row.position}</td>
                <td className="py-2 pl-2 text-left">
                  <span style={{ color: isHighlighted ? "var(--ink)" : "var(--ink-2)", fontWeight: isHighlighted ? 600 : 400 }}>
                    {row.team_name || "—"}
                  </span>
                </td>
                {[
                  row.won == null ? null : row.won + (row.drawn ?? 0) + (row.lost ?? 0),
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
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="section-label">Current Trends</h3>
        <SectionBadge label="LIVESCORES & EVENTS • football-data.org" />
      </div>
      <div className="grid grid-cols-2 gap-6">
        {[{ name: teamA, items: trends.team_a }, { name: teamB, items: trends.team_b }].map(({ name, items }) => (
          <div key={name}>
            <p className="text-xs font-semibold mb-2 break-words" style={{ color: "var(--muted)" }}>{name}</p>
            {items.length === 0 ? (
              <p className="text-xs" style={{ color: "var(--muted-2)" }}>No trend data</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {items.map((t, i) => (
                  <span key={i} className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs"
                    style={{ border: "1px solid var(--primary-edge)", background: "var(--primary-soft)", color: "var(--primary-text)" }}>
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
    <div className="card p-6">
      <h3 className="section-label mb-4">AI Reasoning Breakdown</h3>
      {chips.length > 0 ? (
        <div className="space-y-3 mb-4">
          {chips.map((chip, i) => (
            <div key={i} className="insight-chip">
              <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md"
                style={{ background: "var(--primary-soft)", border: "1px solid var(--primary-edge)" }}>
                <span className="text-xs font-bold" style={{ color: "var(--primary-text)" }}>{i + 1}</span>
              </div>
              <div>
                <p className="text-xs font-semibold mb-0.5" style={{ color: "var(--primary-text)" }}>{chip.label}</p>
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
          <summary className="hover-accent cursor-pointer text-xs transition-colors select-none py-1.5"
            style={{ color: "var(--muted-2)" }}
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
    <div className="card p-6">
      <h3 className="section-label mb-4">Key Factors</h3>
      <div className="space-y-3">
        {keyFactors.map((kf, i) => (
          <div key={i} className="flex items-start gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-xs font-bold"
              style={{ background: "var(--primary-soft)", border: "1px solid var(--border-s)", color: "var(--primary-text)" }}>
              {i + 1}
            </span>
            <div>
              <p className="text-xs font-semibold mb-0.5" style={{ color: "var(--primary-text)" }}>{kf.title}</p>
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
    <div className="card p-6">
      <h3 className="section-label mb-4">Prediction Summary</h3>
      <dl className="space-y-3">
        {[
          { term: "Predicted Winner", value: prediction.winner || "Unknown" },
          { term: "Confidence", value: prediction.confidence ? prediction.confidence.charAt(0).toUpperCase() + prediction.confidence.slice(1) : "Unknown" },
          { term: "Probabilities", value: prediction.probabilityMethod === "confidence-estimate" ? "Estimate (standings unavailable)" : "Dixon-Coles model" },
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
    <div className="card p-6 border-dashed" style={{ borderColor: "var(--primary-edge)" }}>
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg mt-0.5"
          style={{ background: "var(--primary-soft)", border: "1px solid var(--primary-edge)" }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ color: "var(--primary-text)" }}>
            <path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <div>
          <h4 className="font-semibold text-sm mb-1" style={{ color: "var(--ink)" }}>About this data</h4>
          <p className="text-xs leading-relaxed" style={{ color: "var(--muted)" }}>
            Recent form, standings and top scorers come from football-data.org. Injuries, lineups, xG and head-to-head records aren&apos;t available on this data plan, so this prediction doesn&apos;t account for them.
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
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color:"var(--primary-text)" }}>
            <circle cx="12" cy="12" r="10"/>
            <path d="M12 2a10 10 0 0 0-6.88 2.77L12 12l7.47-4.5A10 10 0 0 0 12 2z" fill="currentColor" fillOpacity="0.4"/>
          </svg>
        </div>
      </div>
      <h3 style={{ fontSize:22, fontWeight:600, letterSpacing:"-0.02em", color:"var(--ink)", marginBottom:8, fontFamily:"var(--font-display), system-ui" }}>
        Analysing {home} vs {away}
      </h3>
      <p style={{ fontSize:14, color:"var(--muted)", marginBottom:36, maxWidth:400 }}>
        The model is working out the probabilities and Gemini is explaining them from standings, recent form and top scorers. This may take 20–40 seconds.
      </p>
      <div style={{ display:"flex", flexDirection:"column", gap:10, width:"100%", maxWidth:360 }}>
        {STEPS.map((label, i) => {
          const done = i < step;
          const active = i === step;
          return (
            <div key={label} style={{
              display:"flex", alignItems:"center", gap:12, padding:"11px 16px", borderRadius:12,
              background: done ? "var(--primary-soft)" : active ? "var(--primary-soft)" : "var(--surface)",
              border: `1px solid ${done ? "var(--primary-soft)" : active ? "var(--primary-edge)" : "var(--border)"}`,
              transition:"background-color 0.35s ease, border-color 0.35s ease",
            }}>
              <div style={{
                width:22, height:22, borderRadius:"50%", flexShrink:0, display:"grid", placeItems:"center",
                background: done ? "var(--primary-text)" : active ? "var(--primary)" : "var(--surface-2)",
                transition:"background 0.3s ease",
              }}>
                {done ? (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--on-accent)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
                ) : active ? (
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="var(--on-accent)" style={{ animation:"orbSpin 0.8s linear infinite" }}><path d="M12 2 14 9l7 2-7 2-2 7-2-7-7-2 7-2 2-7Z" /></svg>
                ) : (
                  <span style={{ width:6, height:6, borderRadius:"50%", background:"var(--border-s)" }} />
                )}
              </div>
              <span style={{ fontSize:13, fontWeight:500, color: done ? "var(--primary-text)" : active ? "var(--primary-text)" : "var(--muted)", transition:"color 0.3s ease" }}>
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
  const { user, emailVerified } = useAuth();

  const [fixture, setFixture] = useState<Fixture | null>(null);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [enriched, setEnriched] = useState<EnrichedData | null>(null);
  const [enrichedLoading, setEnrichedLoading] = useState(false);
  const [pageState, setPageState] = useState<PageState>("loadingFixture");
  const [errorMsg, setErrorMsg] = useState("");
  const [allowance, setAllowance] = useState<PredictionAllowance | null>(null);

  // Display only: the backend enforces the caps, so a failed read just hides the line.
  const refreshAllowance = useCallback(async () => {
    if (!user) return;
    try {
      const res = await getPredictionAllowance(await user.getIdToken());
      setAllowance(res.data);
    } catch {
      setAllowance(null);
    }
  }, [user]);

  useEffect(() => {
    if (emailVerified) refreshAllowance();
  }, [emailVerified, refreshAllowance]);

  const loadFixture = useCallback(async () => {
    setPageState("loadingFixture");
    try {
      const res = await getFixtureById(matchId);
      setFixture(res.data as Fixture);
      setPageState("ready");
    } catch (err: unknown) {
      setErrorMsg(describeApiError(err, "This match couldn't be found. It may no longer be on the schedule."));
      setPageState("error");
    }
  }, [matchId]);

  useEffect(() => { loadFixture(); }, [loadFixture]);

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
      const msg = err instanceof Error ? err.message : "";
      const detail = describeApiError(err, "The prediction didn't finish. Try again in a minute.");
      // The HTTP status, not a search of the text: details can quote other codes.
      const httpStatus = msg.match(/^API (\d+):/)?.[1];
      if (httpStatus === "501") {
        setErrorMsg("This match has no live data behind it, so it can't be predicted. Pick another from the match list.");
        setPageState("unavailable");
      } else if (httpStatus === "403" || httpStatus === "429") {
        // Access gate or daily prediction limit — show the backend's reason.
        setErrorMsg(detail);
        setPageState("unavailable");
      } else {
        setErrorMsg(detail);
        setPageState("error");
      }
    } finally {
      refreshAllowance();
    }
  };

  const outOfPredictions = allowance?.remaining === 0;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const keyFactors = (prediction as any)?.keyFactors as Array<{ title: string; text: string }> | undefined;

  return (
    <div className="min-h-[100dvh]">
      <Navbar />

      <main>
      <div className="relative pt-[calc(80px+env(safe-area-inset-top,0px))]">
        <div className="relative mx-auto max-w-4xl px-[clamp(16px,4vw,32px)] pt-10 pb-4">
          <Link href="/dashboard" className="hover-accent mb-4 inline-flex items-center gap-1.5 min-h-[24px] text-sm transition-colors"
            style={{ color: "var(--muted)" }}
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

      <div className="mx-auto max-w-4xl px-[clamp(16px,4vw,32px)] pb-16 space-y-4">

        {pageState === "loadingFixture" && <PredictionSkeleton />}

        {pageState === "ready" && fixture && (
          <div className="space-y-4">
            <MatchHeaderCard fixture={fixture} />
            <div className="card p-6 flex flex-col items-center text-center gap-5">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl"
                style={{ background: "var(--primary-soft)", border: "1px solid var(--primary-edge)" }}>
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" style={{ color: "var(--primary-text)" }}>
                  <path d="M13 10V3L4 14h7v7l9-11h-7z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              {emailVerified ? (
                <>
                  <div>
                    <h2 className="text-xl font-bold" style={{ color: "var(--ink)", fontFamily: "var(--font-display), system-ui" }}>Ready to predict</h2>
                    <p className="mt-1.5 text-sm max-w-xs" style={{ color: "var(--muted)" }}>
                      A statistical model works out the probabilities from league standings, then Gemini AI explains them using standings, recent form and top scorers.
                    </p>
                  </div>
                  <button onClick={handlePredict} disabled={outOfPredictions} className="btn-primary text-base px-10 py-3.5">
                    Generate AI Prediction
                  </button>
                  <AllowanceBadge allowance={allowance} />
                </>
              ) : (
                <VerifyEmailNotice />
              )}
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

              {prediction.headToHead && prediction.headToHead.total > 0 && (
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

              <div className="flex flex-col items-center gap-2 pt-2">
                <button onClick={handlePredict} disabled={outOfPredictions} className="btn-ghost text-sm px-6 py-2.5">
                  Regenerate prediction
                </button>
                <AllowanceBadge allowance={allowance} />
              </div>

              <Disclaimer />
            </motion.div>
          </AnimatePresence>
        )}

        {pageState === "unavailable" && (
          <div className="card p-6 flex flex-col items-center text-center gap-4" style={{ borderColor: "var(--orange-soft)" }}>
            <div className="flex h-14 w-14 items-center justify-center rounded-full" style={{ background: "var(--orange-soft)", border: "1px solid var(--orange-edge)" }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" style={{ color: "var(--orange)" }}>
                <path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div>
              <h3 className="font-semibold" style={{ color: "var(--ink)" }}>Prediction Unavailable</h3>
              <p className="mt-2 text-sm max-w-sm" style={{ color: "var(--muted)" }}>
                {errorMsg || "This match can't be predicted right now. Pick another from the match list."}
              </p>
            </div>
            <Link href="/dashboard" className="btn-ghost text-sm px-6 py-2.5">← Back to matches</Link>
          </div>
        )}

        {pageState === "error" && (
          <ErrorState
            title={fixture ? "The prediction didn't finish" : "We can't load this match"}
            message={errorMsg}
            onRetry={fixture ? handlePredict : loadFixture}
          />
        )}
      </div>
      </main>
    </div>
  );
}

export default function PredictionPage({ params }: { params: { matchId: string } }) {
  return (
    <ProtectedRoute>
      <MotionConfig reducedMotion="user">
        <PredictionContent matchId={params.matchId} />
      </MotionConfig>
    </ProtectedRoute>
  );
}
