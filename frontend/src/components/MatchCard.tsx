"use client";

import Link from "next/link";
import { useState } from "react";
import type { Fixture } from "@/lib/types";
import { getTeamColor } from "@/lib/teamColors";
import { parseFixtureDate, formatLATime, formatLADateLabel, formatLADateLong } from "@/lib/dateUtils";

interface Props {
  fixture: Fixture;
  leagueAccent?: string;
}

function formatKickoff(isoString: string): { dateLabel: string; time: string; fullDate: string } {
  try {
    const d = parseFixtureDate(isoString);
    return {
      dateLabel: formatLADateLabel(d),   // "TODAY" | "TOMORROW" | "Sat, May 17, 2026"
      time: formatLATime(d),             // "5:30 PM PDT"
      fullDate: formatLADateLong(d),     // "Saturday, May 16, 2026"
    };
  } catch {
    return { dateLabel: "—", time: "—", fullDate: "—" };
  }
}

function StatusChip({ status }: { status: string }) {
  const s = status?.toLowerCase() ?? "";
  const isLive = s === "inplay" || s === "live" || s === "halftime";
  const isFinished = ["finished", "ft", "aet", "pen"].includes(s);

  if (isLive) {
    return (
      <span style={{
        display: "inline-flex", alignItems: "center", gap: 5,
        fontSize: 10, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase",
        color: "#4ADE80", background: "rgba(34,197,94,0.12)", border: "1px solid rgba(34,197,94,0.3)",
        borderRadius: 999, padding: "3px 9px",
      }}>
        <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#22C55E", boxShadow: "0 0 6px #22C55E", display: "inline-block" }} />
        {s === "halftime" ? "Half-time" : "Live"}
      </span>
    );
  }
  if (isFinished) {
    return (
      <span style={{
        fontSize: 10, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase",
        color: "var(--muted-2)", background: "var(--surface-2)", border: "1px solid var(--border-s)",
        borderRadius: 999, padding: "3px 9px",
      }}>
        Full-time
      </span>
    );
  }
  return (
    <span style={{
      fontSize: 10, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase",
      color: "var(--accent-2)", background: "var(--accent-soft)", border: "1px solid var(--accent-edge)",
      borderRadius: 999, padding: "3px 9px",
    }}>
      Upcoming
    </span>
  );
}

function TeamBadge({ name, logo, primary }: { name: string; logo?: string; primary: string }) {
  const [imgError, setImgError] = useState(false);
  const { abbr } = getTeamColor(name);

  const useLogo = logo && !imgError;

  return (
    <div style={{
      width: 52, height: 52, borderRadius: 14, flexShrink: 0,
      background: useLogo ? "rgba(255,255,255,0.06)" : `${primary}22`,
      border: `1px solid ${primary}44`,
      display: "grid", placeItems: "center",
      boxShadow: `0 2px 12px -4px ${primary}55`,
    }}>
      {useLogo ? (
        <img
          src={logo}
          alt={name}
          width={32}
          height={32}
          style={{ objectFit: "contain", display: "block" }}
          onError={() => setImgError(true)}
        />
      ) : (
        <span style={{ fontSize: 13, fontWeight: 800, letterSpacing: "0.04em", color: primary }}>
          {abbr}
        </span>
      )}
    </div>
  );
}

export default function MatchCard({ fixture, leagueAccent = "#8B5CF6" }: Props) {
  const s = fixture.status?.toLowerCase() ?? "";
  const isLive = s === "inplay" || s === "live" || s === "halftime";
  const isFinished = ["finished", "ft", "aet", "pen"].includes(s);
  const canPredict = !isFinished;

  const homeColors = getTeamColor(fixture.homeTeam.name);
  const awayColors = getTeamColor(fixture.awayTeam.name);

  const score = fixture.score;
  const homeWin = score ? score.home > score.away : false;
  const awayWin = score ? score.away > score.home : false;

  const { dateLabel, time, fullDate } = formatKickoff(fixture.startingAt);

  return (
    <article
      style={{
        background: "var(--surface)",
        borderRadius: 18,
        boxShadow: "inset 0 0 0 1px var(--border)",
        overflow: "hidden",
        position: "relative",
        transition: "box-shadow 0.2s ease, transform 0.2s ease",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.boxShadow = `inset 0 0 0 1px ${leagueAccent}55, 0 12px 40px -16px ${leagueAccent}44`;
        (e.currentTarget as HTMLElement).style.transform = "translateY(-2px)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.boxShadow = "inset 0 0 0 1px var(--border)";
        (e.currentTarget as HTMLElement).style.transform = "translateY(0)";
      }}
    >
      {/* Colored top strip */}
      <div style={{ height: 3, background: `linear-gradient(90deg, transparent, ${leagueAccent} 30%, ${leagueAccent} 70%, transparent)` }} />

      {/* Subtle glow */}
      <div aria-hidden style={{
        position: "absolute", inset: 0, pointerEvents: "none",
        background: `radial-gradient(55% 35% at 100% 0%, ${leagueAccent}08, transparent 60%)`,
      }} />

      <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 14, position: "relative" }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 7, height: 7, borderRadius: 2, background: leagueAccent, flexShrink: 0, display: "inline-block" }} />
            <span style={{ fontSize: 11, fontWeight: 600, color: "var(--muted)", letterSpacing: "0.02em" }}>
              {fixture.leagueName}
            </span>
          </div>
          <StatusChip status={fixture.status ?? "NS"} />
        </div>

        {/* Teams + score/time */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {/* Home team */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 6, minWidth: 0 }}>
            <TeamBadge name={fixture.homeTeam.name} logo={fixture.homeTeam.logo} primary={homeColors.primary} />
            <div>
              <p style={{
                fontSize: 13, fontWeight: isFinished && homeWin ? 700 : 600, margin: 0, lineHeight: 1.3,
                color: isFinished && awayWin ? "var(--muted-2)" : "var(--ink)",
                whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
              }}>
                {fixture.homeTeam.name}
              </p>
              <p style={{ fontSize: 11, color: "var(--muted-2)", margin: "2px 0 0" }}>Home</p>
            </div>
          </div>

          {/* Center: score or kickoff time */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3, flexShrink: 0, minWidth: 100, textAlign: "center" }}>
            {(isLive || isFinished) && score ? (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 26, fontWeight: 800, lineHeight: 1, color: homeWin ? "var(--ink)" : awayWin ? "var(--muted-2)" : "var(--ink)" }}>
                    {score.home}
                  </span>
                  <span style={{ fontSize: 16, fontWeight: 500, color: "var(--muted-2)" }}>—</span>
                  <span style={{ fontSize: 26, fontWeight: 800, lineHeight: 1, color: awayWin ? "var(--ink)" : homeWin ? "var(--muted-2)" : "var(--ink)" }}>
                    {score.away}
                  </span>
                </div>
                <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: isLive ? "#4ADE80" : "var(--muted-2)", opacity: 0.8 }}>
                  {isLive ? "LIVE" : "FT"}
                </span>
              </>
            ) : (
              <>
                {/* e.g. "TODAY" or "TOMORROW" or "Sat, May 17, 2026" */}
                <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.08em", color: "var(--accent-2)", textTransform: "uppercase" }}>
                  {dateLabel}
                </span>
                {/* e.g. "5:30 PM PDT" */}
                <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.1, letterSpacing: "-0.01em", color: "var(--ink)", whiteSpace: "nowrap" }}>
                  {time}
                </span>
              </>
            )}
          </div>

          {/* Away team */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6, minWidth: 0 }}>
            <TeamBadge name={fixture.awayTeam.name} logo={fixture.awayTeam.logo} primary={awayColors.primary} />
            <div style={{ textAlign: "right" }}>
              <p style={{
                fontSize: 13, fontWeight: isFinished && awayWin ? 700 : 600, margin: 0, lineHeight: 1.3,
                color: isFinished && homeWin ? "var(--muted-2)" : "var(--ink)",
                whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
              }}>
                {fixture.awayTeam.name}
              </p>
              <p style={{ fontSize: 11, color: "var(--muted-2)", margin: "2px 0 0" }}>Away</p>
            </div>
          </div>
        </div>

        {/* Footer: date + venue + CTA */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, paddingTop: 4, borderTop: "1px solid var(--border)" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0, overflow: "hidden" }}>
            {/* Always show full date + time — "Saturday, May 16, 2026 · 5:30 PM PDT" */}
            <span style={{ fontSize: 11, color: "var(--muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {fullDate}{!isFinished && !isLive ? ` · ${time}` : ""}
            </span>
            {/* Venue */}
            {fixture.venue && (
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--muted-2)", flexShrink: 0 }}>
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" />
                </svg>
                <span style={{ fontSize: 10, color: "var(--muted-2)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {fixture.venue}
                </span>
              </div>
            )}
          </div>

          <Link
            href={`/prediction/${fixture.id}`}
            style={{
              display: "inline-flex", alignItems: "center", gap: 5, flexShrink: 0,
              padding: "8px 14px", borderRadius: 10,
              fontSize: 12, fontWeight: 600,
              textDecoration: "none",
              transition: "opacity 0.15s ease",
              ...(canPredict
                ? {
                    background: `linear-gradient(180deg, ${leagueAccent}CC, ${leagueAccent})`,
                    color: "white",
                    boxShadow: `0 6px 16px -6px ${leagueAccent}88, inset 0 1px 0 rgba(255,255,255,0.2)`,
                  }
                : isFinished
                ? {
                    background: "var(--surface-2)",
                    color: "var(--muted)",
                    boxShadow: `inset 0 0 0 1px ${leagueAccent}33`,
                  }
                : {
                    background: "var(--surface-2)",
                    color: "var(--muted-2)",
                    boxShadow: "inset 0 0 0 1px var(--border)",
                  }),
            }}
          >
            {canPredict ? (
              <>
                <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2 14 9l7 2-7 2-2 7-2-7-7-2 7-2 2-7Z" />
                </svg>
                Predict
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12h14M13 5l7 7-7 7" />
                </svg>
              </>
            ) : isFinished ? (
              "Full time"
            ) : (
              "Preview only"
            )}
          </Link>
        </div>
      </div>
    </article>
  );
}
