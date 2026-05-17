"use client";

import { useEffect, useRef, useState } from "react";

export type DateTab = "today" | "tomorrow";

interface Props {
  search: string;
  onSearchChange: (v: string) => void;
  league: string;
  onLeagueChange: (v: string) => void;
  leagues: string[];
  tab: DateTab;
  onTabChange: (v: DateTab) => void;
}

function LeagueIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="8" r="6" /><path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11" />
    </svg>
  );
}

const LEAGUE_COLORS: Record<string, string> = {
  "Premier League": "#9381FF",
  "La Liga": "#EE8707",
  "Serie A": "#4A9FFF",
  "Bundesliga": "#D4021D",
  "Ligue 1": "#4A9FFF",
  "Major League Soccer": "#E82E2E",
};

export default function FilterBar({ search, onSearchChange, league, onLeagueChange, leagues, tab, onTabChange }: Props) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!dropRef.current?.contains(e.target as Node)) setDropdownOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div
      style={{
        position: "sticky",
        top: 60,
        zIndex: 30,
        background: "color-mix(in srgb, var(--bg) 85%, transparent)",
        backdropFilter: "saturate(180%) blur(20px)",
        WebkitBackdropFilter: "saturate(180%) blur(20px)",
        borderBottom: "1px solid var(--border)",
      }}
    >
      <div
        style={{
          maxWidth: 1240,
          margin: "0 auto",
          padding: "10px 32px",
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        {/* Search */}
        <div style={{ flex: 1, position: "relative", maxWidth: 440 }}>
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--muted-2)", pointerEvents: "none" }}
          >
            <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
          </svg>
          <input
            type="text"
            placeholder="Search clubs or leagues…"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            style={{
              width: "100%",
              padding: "9px 14px 9px 36px",
              background: "var(--surface)",
              border: "1px solid var(--border-s)",
              borderRadius: 10,
              color: "var(--ink)",
              fontSize: 13,
              outline: "none",
              transition: "border-color 0.15s",
              boxSizing: "border-box",
            }}
            onFocus={(e) => (e.currentTarget.style.borderColor = "var(--accent-edge)")}
            onBlur={(e) => (e.currentTarget.style.borderColor = "var(--border-s)")}
          />
        </div>

        {/* League dropdown */}
        <div ref={dropRef} style={{ position: "relative" }}>
          <button
            onClick={() => setDropdownOpen((o) => !o)}
            style={{
              display: "flex", alignItems: "center", gap: 7,
              padding: "9px 14px", borderRadius: 10,
              background: league ? "var(--accent-soft)" : "var(--surface)",
              border: `1px solid ${league ? "var(--accent-edge)" : "var(--border-s)"}`,
              color: league ? "var(--accent-2)" : "var(--ink-2)",
              fontSize: 13, fontWeight: 500, cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            <LeagueIcon />
            {league || "All leagues"}
            <svg
              width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
              strokeLinecap="round" strokeLinejoin="round"
              style={{ transform: dropdownOpen ? "rotate(180deg)" : "none", transition: "transform 0.15s" }}
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>

          {dropdownOpen && (
            <div
              style={{
                position: "absolute", top: "calc(100% + 8px)", left: 0,
                minWidth: 180,
                background: "var(--surface)",
                borderRadius: 12,
                boxShadow: "0 16px 40px -12px rgba(0,0,0,0.5), inset 0 0 0 1px var(--border-s)",
                padding: "6px",
                zIndex: 50,
                animation: "dropIn 0.15s cubic-bezier(0.16,1,0.3,1)",
              }}
            >
              <style>{`@keyframes dropIn{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:translateY(0)}}`}</style>

              {/* All leagues */}
              <button
                onClick={() => { onLeagueChange(""); setDropdownOpen(false); }}
                style={{
                  width: "100%", display: "flex", alignItems: "center", gap: 8,
                  padding: "8px 10px", borderRadius: 8, border: "none", cursor: "pointer",
                  fontSize: 13, color: !league ? "var(--accent-2)" : "var(--ink-2)",
                  background: !league ? "var(--accent-soft)" : "none",
                  textAlign: "left", fontWeight: !league ? 600 : 400,
                }}
              >
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--muted-2)", display: "inline-block" }} />
                All leagues
              </button>

              {leagues.map((l) => (
                <button
                  key={l}
                  onClick={() => { onLeagueChange(l); setDropdownOpen(false); }}
                  style={{
                    width: "100%", display: "flex", alignItems: "center", gap: 8,
                    padding: "8px 10px", borderRadius: 8, border: "none", cursor: "pointer",
                    fontSize: 13, color: league === l ? "var(--accent-2)" : "var(--ink-2)",
                    background: league === l ? "var(--accent-soft)" : "none",
                    textAlign: "left", fontWeight: league === l ? 600 : 400,
                  }}
                  onMouseEnter={(e) => { if (league !== l) (e.currentTarget as HTMLElement).style.background = "var(--surface-2)"; }}
                  onMouseLeave={(e) => { if (league !== l) (e.currentTarget as HTMLElement).style.background = "none"; }}
                >
                  <span style={{
                    width: 8, height: 8, borderRadius: "50%",
                    background: LEAGUE_COLORS[l] ?? "#8B5CF6",
                    display: "inline-block", flexShrink: 0,
                  }} />
                  {l}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Date tabs */}
        <div
          style={{
            display: "flex",
            background: "var(--surface)",
            border: "1px solid var(--border-s)",
            borderRadius: 10,
            padding: 3,
            gap: 2,
          }}
        >
          {([["today", "Today"], ["tomorrow", "Tomorrow"]] as [DateTab, string][]).map(([t, label]) => (
            <button
              key={t}
              onClick={() => onTabChange(t)}
              style={{
                padding: "6px 14px", borderRadius: 7, border: "none", cursor: "pointer",
                fontSize: 13, fontWeight: tab === t ? 600 : 400,
                color: tab === t ? "var(--ink)" : "var(--muted)",
                background: tab === t ? "var(--surface-3, #1E1E2E)" : "none",
                boxShadow: tab === t ? "0 1px 4px rgba(0,0,0,0.3)" : "none",
                transition: "all 0.15s ease",
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
