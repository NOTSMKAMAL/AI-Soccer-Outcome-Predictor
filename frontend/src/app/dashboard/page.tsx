"use client";

import { useEffect, useMemo, useState } from "react";
import ProtectedRoute from "@/components/ProtectedRoute";
import Navbar from "@/components/Navbar";
import FilterBar, { type DateTab } from "@/components/FilterBar";
import MatchCard from "@/components/MatchCard";
import { MatchCardSkeleton } from "@/components/LoadingSkeleton";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import { getTopLeagueFixtures } from "@/lib/api";
import { MOCK_FIXTURES } from "@/lib/mockData";
import type { Fixture } from "@/lib/types";
import { parseFixtureDate, toLADateStr, todayLA, tomorrowLA } from "@/lib/dateUtils";

type LoadState = "loading" | "success" | "error";

const LEAGUE_ACCENTS: Record<string, string> = {
  "Major League Soccer":   "#E82E2E",
  "MLS":                   "#E82E2E",
  "Premier League":        "#9381FF",
  "La Liga":               "#EE8707",
  "Serie A":               "#4A9FFF",
  "Bundesliga":            "#D4021D",
  "Ligue 1":               "#4A9FFF",
  "Champions League":      "#001F5C",
  "UEFA Champions League": "#001F5C",
};
const DEFAULT_ACCENT = "#8B5CF6";

function getAccent(leagueName: string): string {
  const key = Object.keys(LEAGUE_ACCENTS).find((k) =>
    leagueName?.toLowerCase().includes(k.toLowerCase())
  );
  return key ? LEAGUE_ACCENTS[key] : DEFAULT_ACCENT;
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

function StatsRow({ fixtures, isLive }: { fixtures: Fixture[]; isLive: boolean }) {
  const liveCount = fixtures.filter((f) =>
    ["live", "inplay", "halftime"].includes(f.status?.toLowerCase() ?? "")
  ).length;
  const leagueCount = new Set(fixtures.map((f) => f.leagueName)).size;

  const stats = [
    { label: "Matches available", value: fixtures.length, accent: "var(--accent-2)" },
    { label: "Live now",          value: liveCount, accent: "#34D399", live: liveCount > 0 },
    { label: "Leagues covered",   value: leagueCount || "—", accent: "#60A5FA" },
    { label: "Data source",       value: isLive ? "Live" : "Preview", accent: isLive ? "#34D399" : "#FACC15" },
  ];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 28 }}>
      {stats.map((s) => (
        <div key={s.label} style={{
          background: "var(--surface)", borderRadius: 14, padding: "16px 20px",
          boxShadow: "inset 0 0 0 1px var(--border)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--muted)", marginBottom: 6 }}>
            {s.live && <span className="live-dot" style={{ width: 6, height: 6 }} />}
            {s.label}
          </div>
          <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.025em", color: s.accent }}>
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

  // Filter state
  const [search, setSearch] = useState("");
  const [league, setLeague] = useState("");
  const [tab, setTab] = useState<DateTab>("today");

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
        else if (source === "sportmonks") setIsLiveData(true);
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

  // Derive available leagues from fixtures
  const availableLeagues = useMemo(() => {
    const set = new Set(fixtures.map((f) => f.leagueName).filter(Boolean));
    return Array.from(set).sort();
  }, [fixtures]);

  // Apply filters
  const filtered = useMemo(() => {
    let list = fixtures;

    // Filter by LA calendar date — uses America/Los_Angeles so DST is automatic
    const targetDate = tab === "today" ? todayLA() : tomorrowLA();
    list = list.filter((f) => toLADateStr(parseFixtureDate(f.startingAt)) === targetDate);

    // League
    if (league) list = list.filter((f) => f.leagueName === league);

    // Search
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

  const grouped = groupByLeague(filtered);

  return (
    <div style={{ minHeight: "100vh", paddingTop: 60 }}>
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
        <div aria-hidden style={{
          position: "absolute", inset: "0 0 auto 0", height: 180,
          background: "radial-gradient(ellipse 70% 40% at 50% 0%, rgba(124,58,237,0.10) 0%, transparent 70%)",
          pointerEvents: "none",
        }} />
        <div style={{ position: "relative", maxWidth: 1240, margin: "0 auto", padding: "28px 32px 20px" }}>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 16, marginBottom: 24 }}>
            <div>
              <h1 style={{ fontSize: "clamp(20px,3.5vw,28px)", fontWeight: 700, letterSpacing: "-0.025em", margin: "0 0 4px", color: "var(--ink)" }}>
                {tab === "today" ? "Today's Fixtures" : "Tomorrow's Fixtures"}
              </h1>
              <p style={{ fontSize: 13, color: "var(--muted)", margin: 0 }}>
                Select a fixture to generate an AI-powered match prediction.
              </p>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
              {isLiveData && (
                <span className="badge-live">
                  <span className="live-dot" style={{ width: 6, height: 6 }} />
                  SportMonks Live
                </span>
              )}
              {isMockData && !isLiveData && (
                <span className="badge-preview">
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#FCD34D", display: "inline-block" }} />
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
            <StatsRow fixtures={filtered} isLive={isLiveData} />
          )}
        </div>
      </div>

      {/* Main content */}
      <div style={{ maxWidth: 1240, margin: "0 auto", padding: "0 32px 64px" }}>
        {/* Mock warning */}
        {isMockData && state !== "error" && (
          <div style={{
            display: "flex", alignItems: "center", gap: 12, marginBottom: 20,
            padding: "12px 16px", borderRadius: 12,
            border: "1px solid rgba(251,191,36,0.2)", background: "rgba(251,191,36,0.06)",
          }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0, color: "#FCD34D" }}>
              <path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
                stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <p style={{ margin: 0, fontSize: 13, color: "#FCD34D" }}>
              Showing preview fixtures because live SportMonks data is not available.
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
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: 14 }}>
            {Array.from({ length: 6 }).map((_, i) => <MatchCardSkeleton key={i} />)}
          </div>
        )}

        {/* Fixture grid */}
        {state !== "loading" && filtered.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 36 }}>
            {Object.entries(grouped).map(([leagueName, leagueFixtures]) => {
              const accent = getAccent(leagueName);
              return (
                <section key={leagueName}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
                    <div style={{ width: 4, height: 22, borderRadius: 2, background: accent, flexShrink: 0 }} />
                    <h2 style={{ fontWeight: 700, fontSize: 15, color: "var(--ink)", margin: 0 }}>{leagueName}</h2>
                    <div style={{ flex: 1, height: 1, background: "linear-gradient(to right, var(--border-s), transparent)" }} />
                    <span style={{ fontSize: 12, color: "var(--muted-2)" }}>
                      {leagueFixtures.length} {leagueFixtures.length === 1 ? "fixture" : "fixtures"}
                    </span>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 12 }}>
                    {leagueFixtures.map((f) => (
                      <MatchCard key={f.id} fixture={f} leagueAccent={accent} />
                    ))}
                  </div>
                </section>
              );
            })}
          </div>
        )}

        {/* Empty for filtered view */}
        {state === "success" && filtered.length === 0 && fixtures.length > 0 && (() => {
          const dayLabel = tab === "today" ? "today" : "tomorrow";
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

        {/* No data at all */}
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
