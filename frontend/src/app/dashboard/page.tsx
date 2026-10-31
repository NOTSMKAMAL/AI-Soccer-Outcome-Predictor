"use client";

import { useEffect, useMemo, useState } from "react";
import ProtectedRoute from "@/components/ProtectedRoute";
import Navbar, { NAVBAR_HEIGHT } from "@/components/Navbar";
import FilterBar, { type DateTab } from "@/components/FilterBar";
import MatchCard from "@/components/MatchCard";
import { MatchCardSkeleton } from "@/components/LoadingSkeleton";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import { getTopLeagueFixtures } from "@/lib/api";
import { MOCK_FIXTURES } from "@/lib/mockData";
import type { Fixture } from "@/lib/types";
import { parseFixtureDate, toLADateStr, isUpcomingLA } from "@/lib/dateUtils";

type LoadState = "loading" | "success" | "error";

// 16px on phones, growing to 32px on desktop.
const SIDE_GUTTER = "clamp(16px, 4vw, 32px)";

const LIVE_STATUSES = ["live", "inplay", "halftime"];

function isLiveFixture(f: Fixture): boolean {
  return LIVE_STATUSES.includes(f.status?.toLowerCase() ?? "");
}

const FINISHED_STATUSES = ["finished", "ft", "aet", "pen"];

// Not started yet, kicking off today or later. Status matters as well as date:
// the backend keeps matches that finished earlier today.
function isUpcomingFixture(f: Fixture): boolean {
  const status = f.status?.toLowerCase() ?? "";
  if (LIVE_STATUSES.includes(status) || FINISHED_STATUSES.includes(status)) return false;
  return isUpcomingLA(parseFixtureDate(f.startingAt));
}

function groupByLeague(fixtures: Fixture[]): Record<string, Fixture[]> {
  return fixtures.reduce<Record<string, Fixture[]>>((acc, f) => {
    const key = f.leagueName ?? "Other";
    if (!acc[key]) acc[key] = [];
    acc[key].push(f);
    return acc;
  }, {});
}

// ── Stats row ──────────────────────────────────────────────────────────────────

// `liveCount` is passed in rather than derived from `fixtures`: `fixtures` is the
// tab-filtered list, and the Upcoming tab never contains live matches.
function StatsRow({ fixtures, liveCount, isLive }: { fixtures: Fixture[]; liveCount: number; isLive: boolean }) {
  const leagueCount = new Set(fixtures.map((f) => f.leagueName)).size;

  const stats = [
    { label: "Matches available", value: fixtures.length, accent: "var(--primary-text)" },
    { label: "Live now",          value: liveCount, accent: "var(--primary-text)", live: liveCount > 0 },
    { label: "Leagues covered",   value: leagueCount || "—", accent: "var(--ink)" },
    { label: "Data source",       value: isLive ? "Live" : "Preview", accent: isLive ? "var(--primary-text)" : "var(--orange)" },
  ];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12, marginBottom: 28 }}>
      {stats.map((s) => (
        <div key={s.label} style={{
          background: "var(--surface)", borderRadius: 14, padding: "16px 20px",
          boxShadow: "inset 0 0 0 1px var(--border)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--muted)", marginBottom: 6 }}>
            {s.live && <span className="live-dot" style={{ width: 6, height: 6 }} />}
            {s.label}
          </div>
          <div style={{
            fontSize: 26, fontWeight: 700, letterSpacing: "-0.025em",
            color: s.accent, fontFamily: "var(--font-display), system-ui",
          }}>
            {s.value}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Dashboard content ──────────────────────────────────────────────────────────

function DashboardContent() {
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [errorMsg, setErrorMsg] = useState("");
  const [isMockData, setIsMockData] = useState(false);
  const [isLiveData, setIsLiveData] = useState(false);

  const [search, setSearch] = useState("");
  const [league, setLeague] = useState("");
  const [tab, setTab] = useState<DateTab>("upcoming");

  const fetchFixtures = async () => {
    setState("loading");
    setErrorMsg("");
    setIsMockData(false);
    setIsLiveData(false);
    try {
      const res = await getTopLeagueFixtures();
      const data = (res.data ?? []) as Fixture[];
      const source = (res as { source?: string }).source;
      if (data.length === 0) {
        setFixtures(MOCK_FIXTURES);
        setIsMockData(true);
      } else {
        setFixtures(data);
        if (source === "mock") setIsMockData(true);
        else if (source === "football-data" || source === "cache") setIsLiveData(true);
      }
      setState("success");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Backend unreachable.";
      setFixtures(MOCK_FIXTURES);
      setIsMockData(true);
      setErrorMsg(msg);
      setState("error");
    }
  };

  useEffect(() => { fetchFixtures(); }, []);

  const availableLeagues = useMemo(() => {
    const set = new Set(fixtures.map((f) => f.leagueName).filter(Boolean));
    return Array.from(set).sort();
  }, [fixtures]);

  const filtered = useMemo(() => {
    let list = fixtures;
    if (tab === "live") {
      list = list.filter(isLiveFixture);
    } else {
      list = list.filter(isUpcomingFixture);
    }
    if (league) list = list.filter((f) => f.leagueName === league);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((f) =>
        f.homeTeam.name.toLowerCase().includes(q) ||
        f.awayTeam.name.toLowerCase().includes(q) ||
        f.leagueName?.toLowerCase().includes(q)
      );
    }
    return list;
  }, [fixtures, tab, league, search]);

  const liveCount = useMemo(() => fixtures.filter(isLiveFixture).length, [fixtures]);

  const grouped = groupByLeague(filtered);

  return (
    <div style={{ minHeight: "100vh", paddingTop: NAVBAR_HEIGHT }}>
      <Navbar />
      <FilterBar
        search={search}
        onSearchChange={setSearch}
        league={league}
        onLeagueChange={setLeague}
        leagues={availableLeagues}
        tab={tab}
        onTabChange={setTab}
      />

      {/* Hero strip */}
      <div style={{ position: "relative", paddingTop: 24 }}>
        <div style={{ position: "relative", maxWidth: 1240, margin: "0 auto", padding: `28px ${SIDE_GUTTER} 20px` }}>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 16, marginBottom: 24 }}>
            <div>
              <h1 style={{
                fontSize: "clamp(20px,3.5vw,28px)", fontWeight: 700,
                letterSpacing: "-0.025em", margin: "0 0 4px", color: "var(--ink)",
                fontFamily: "var(--font-display), system-ui",
              }}>
                {tab === "live" ? "Live Fixtures" : "Upcoming Fixtures"}
              </h1>
              <p style={{ fontSize: 13, color: "var(--muted)", margin: 0 }}>
                Select a fixture to generate an AI-powered match prediction.
              </p>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
              {isLiveData && (
                <span className="badge-live">
                  <span className="live-dot" style={{ width: 6, height: 6 }} />
                  football-data.org Live
                </span>
              )}
              {isMockData && !isLiveData && (
                <span className="badge-preview">
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--orange)", display: "inline-block" }} />
                  Preview Data
                </span>
              )}
              <span className="badge-gemini">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2 14 9l7 2-7 2-2 7-2-7-7-2 7-2 2-7Z" />
                </svg>
                Gemini AI
              </span>
            </div>
          </div>

          {state !== "loading" && fixtures.length > 0 && (
            <StatsRow fixtures={filtered} liveCount={liveCount} isLive={isLiveData} />
          )}
        </div>
      </div>

      {/* Main content */}
      <div style={{ maxWidth: 1240, margin: "0 auto", padding: `0 ${SIDE_GUTTER} 64px` }}>

        {/* Mock warning */}
        {isMockData && state !== "error" && (
          <div style={{
            display: "flex", alignItems: "center", gap: 12, marginBottom: 20,
            padding: "12px 16px", borderRadius: 12,
            border: "1px solid var(--orange-edge)", background: "var(--orange-soft)",
          }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0, color: "var(--orange)" }}>
              <path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
                stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <p style={{ margin: 0, fontSize: 13, color: "var(--orange)" }}>
              Showing preview fixtures because live football-data.org data is not available.
            </p>
          </div>
        )}

        {/* Error */}
        {state === "error" && (
          <div style={{ marginBottom: 24 }}>
            <ErrorState title="Backend unavailable" message={errorMsg} onRetry={fetchFixtures} />
          </div>
        )}

        {/* Loading */}
        {state === "loading" && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(360px, 100%), 1fr))", gap: 14 }}>
            {Array.from({ length: 6 }).map((_, i) => <MatchCardSkeleton key={i} />)}
          </div>
        )}

        {/* Fixture grid */}
        {state !== "loading" && filtered.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 36 }}>
            {Object.entries(grouped).map(([leagueName, leagueFixtures]) => {
              return (
                <section key={leagueName}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
                    <div style={{ width: 4, height: 22, borderRadius: 2, background: "var(--primary)", flexShrink: 0 }} />
                    <h2 style={{ fontWeight: 700, fontSize: 15, color: "var(--ink)", margin: 0, fontFamily: "var(--font-display), system-ui", letterSpacing: "-0.01em" }}>
                      {leagueName}
                    </h2>
                    <div style={{ flex: 1, height: 1, background: "var(--border-s)" }} />
                    <span style={{ fontSize: 12, color: "var(--muted-2)" }}>
                      {leagueFixtures.length} {leagueFixtures.length === 1 ? "fixture" : "fixtures"}
                    </span>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(340px, 100%), 1fr))", gap: 12 }}>
                    {leagueFixtures.map((f) => (
                      <MatchCard key={f.id} fixture={f} />
                    ))}
                  </div>
                </section>
              );
            })}
          </div>
        )}

        {/* Empty for filtered view */}
        {state === "success" && filtered.length === 0 && fixtures.length > 0 && (() => {
          const dayLabel = tab === "live" ? "live right now" : "the upcoming schedule";
          return (
            <div style={{ textAlign: "center", padding: "60px 0" }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>📅</div>
              <h3 style={{ fontSize: 18, fontWeight: 600, color: "var(--ink)", margin: "0 0 8px" }}>
                {search || league ? "No matches found" : `No fixtures ${dayLabel}`}
              </h3>
              <p style={{ fontSize: 14, color: "var(--muted)", margin: "0 0 20px" }}>
                {search || league
                  ? "Try clearing your search or league filter."
                  : `No matches are scheduled for ${dayLabel} (Pacific time).`}
              </p>
              {(search || league) && (
                <button
                  onClick={() => { setSearch(""); setLeague(""); }}
                  style={{
                    padding: "10px 20px", borderRadius: 10, border: "1px solid var(--border-s)",
                    background: "var(--surface)", color: "var(--ink-2)", fontSize: 13, cursor: "pointer",
                  }}
                >
                  Clear filters
                </button>
              )}
            </div>
          );
        })()}

        {/* No data */}
        {state === "success" && fixtures.length === 0 && (
          <EmptyState title="No fixtures available" message="There are no fixtures scheduled right now. Check back later." />
        )}

        <p style={{ marginTop: 48, textAlign: "center", fontSize: 12, color: "var(--muted-2)" }}>
          Predictions are for analytics and entertainment only. Not betting advice.
        </p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}
