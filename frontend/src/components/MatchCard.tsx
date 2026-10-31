"use client";

import Link from "next/link";
import type { CSSProperties } from "react";
import TeamBadge from "@/components/TeamBadge";
import type { Fixture } from "@/lib/types";
import { parseFixtureDate, formatLATime, formatLADateLabel, formatLADateLong } from "@/lib/dateUtils";

interface Props {
  fixture: Fixture;
}

function formatKickoff(isoString: string): { dateLabel: string; time: string; fullDate: string } {
  try {
    const d = parseFixtureDate(isoString);
    return {
      dateLabel: formatLADateLabel(d),
      time: formatLATime(d),
      fullDate: formatLADateLong(d),
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
        color: "var(--primary-text)", background: "var(--primary-soft)", border: "1px solid var(--primary-edge)",
        borderRadius: 999, padding: "3px 9px",
      }}>
        <span style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--primary)", display: "inline-block" }} />
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
      color: "var(--primary-text)", background: "var(--primary-soft)", border: "1px solid var(--primary-edge)",
      borderRadius: 999, padding: "3px 9px",
    }}>
      Upcoming
    </span>
  );
}

export default function MatchCard({ fixture }: Props) {
  const s = fixture.status?.toLowerCase() ?? "";
  const isLive = s === "inplay" || s === "live" || s === "halftime";
  const isFinished = ["finished", "ft", "aet", "pen"].includes(s);
  // Mock fixtures have no real match behind them, so the backend can never predict them.
  const isPreview = fixture._isMock === true;
  const canPredict = !isFinished && !isPreview;

  const score = fixture.score;
  const homeWin = score ? score.home > score.away : false;
  const awayWin = score ? score.away > score.home : false;

  const { dateLabel, time, fullDate } = formatKickoff(fixture.startingAt);

  const ctaStyle: CSSProperties = {
    display: "inline-flex", alignItems: "center", gap: 5, flexShrink: 0,
    padding: "8px 14px", borderRadius: 10,
    fontSize: 12, fontWeight: 600,
    textDecoration: "none",
    transition: "opacity 0.15s ease, transform 0.15s ease",
    ...(canPredict
      ? {
          background: "var(--primary)",
          color: "var(--on-accent)",
        }
      : isFinished
      ? {
          background: "var(--surface-2)",
          color: "var(--muted)",
          boxShadow: "inset 0 0 0 1px var(--border)",
        }
      : {
          background: "var(--surface-2)",
          color: "var(--muted-2)",
          boxShadow: "inset 0 0 0 1px var(--border)",
        }),
  };

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
        (e.currentTarget as HTMLElement).style.boxShadow = "inset 0 0 0 1px var(--primary-edge)";
        (e.currentTarget as HTMLElement).style.transform = "translateY(-2px)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.boxShadow = "inset 0 0 0 1px var(--border)";
        (e.currentTarget as HTMLElement).style.transform = "translateY(0)";
      }}
    >
      <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 14, position: "relative" }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 7, height: 7, borderRadius: 2, background: "var(--primary)", flexShrink: 0, display: "inline-block" }} />
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
            <TeamBadge name={fixture.homeTeam.name} />
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
                  <span style={{ fontSize: 26, fontWeight: 800, lineHeight: 1, color: homeWin ? "var(--ink)" : awayWin ? "var(--muted-2)" : "var(--ink)", fontFamily: "var(--font-display), system-ui" }}>
                    {score.home}
                  </span>
                  <span style={{ fontSize: 16, fontWeight: 500, color: "var(--muted-2)" }}>—</span>
                  <span style={{ fontSize: 26, fontWeight: 800, lineHeight: 1, color: awayWin ? "var(--ink)" : homeWin ? "var(--muted-2)" : "var(--ink)", fontFamily: "var(--font-display), system-ui" }}>
                    {score.away}
                  </span>
                </div>
                <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: isLive ? "var(--primary-text)" : "var(--muted-2)", opacity: 0.8 }}>
                  {isLive ? "LIVE" : "FT"}
                </span>
              </>
            ) : (
              <>
                <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.08em", color: "var(--muted)", textTransform: "uppercase" }}>
                  {dateLabel}
                </span>
                <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.1, letterSpacing: "-0.01em", color: "var(--ink)", whiteSpace: "nowrap", fontFamily: "var(--font-display), system-ui" }}>
                  {time}
                </span>
              </>
            )}
          </div>

          {/* Away team */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6, minWidth: 0 }}>
            <TeamBadge name={fixture.awayTeam.name} />
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

        {/* Footer */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, paddingTop: 4, borderTop: "1px solid var(--border)" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0, overflow: "hidden" }}>
            <span style={{ fontSize: 11, color: "var(--muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {fullDate}{!isFinished && !isLive ? ` · ${time}` : ""}
            </span>
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

          {isPreview ? (
            <span style={ctaStyle} aria-disabled="true" title="Preview data — live fixtures are needed to predict">
              {isFinished ? "Full time" : "Preview only"}
            </span>
          ) : (
          <Link
            href={`/prediction/${fixture.id}`}
            style={ctaStyle}
            onMouseEnter={(e) => { if (canPredict) (e.currentTarget as HTMLElement).style.transform = "translateY(-1px)"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.transform = "translateY(0)"; }}
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
            ) : (
              "Full time"
            )}
          </Link>
          )}
        </div>
      </div>
    </article>
  );
}
