"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

function FutureFCLogo() {
  return (
    <img
      src="/future-fc-logo.png"
      alt="FUTURE FC"
      width={40}
      height={40}
      style={{
        borderRadius: 4,
        objectFit: "contain",
        flexShrink: 0,
        display: "block",
      }}
    />
  );
}
function LogoutIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
    </svg>
  );
}
function UserMenuIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21a8 8 0 0 0-16 0" /><circle cx="12" cy="7" r="4" />
    </svg>
  );
}
function CloseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}
function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

// ── Account settings modal ────────────────────────────────────────────────────

function AccountSettingsModal({
  user,
  onClose,
}: {
  user: { email: string | null; displayName?: string | null };
  onClose: () => void;
}) {
  const { updateDisplayName } = useAuth();
  const existing = user.displayName ?? "";
  const parts = existing.trim().split(/\s+/);
  const [firstName, setFirstName] = useState(parts[0] ?? "");
  const [lastName, setLastName]   = useState(parts.slice(1).join(" ") ?? "");
  const [busy, setBusy]           = useState(false);
  const [saved, setSaved]         = useState(false);
  const [error, setError]         = useState("");
  const overlayRef = useRef<HTMLDivElement>(null);

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === overlayRef.current) onClose();
  };

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = [firstName.trim(), lastName.trim()].filter(Boolean).join(" ");
    if (!name) { setError("First name is required."); return; }
    setBusy(true);
    setError("");
    try {
      await updateDisplayName(name);
      setSaved(true);
      setTimeout(onClose, 900);
    } catch {
      setError("Failed to update name. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const initial = (existing || user.email || "?")[0].toUpperCase();

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      style={{
        position: "fixed", inset: 0, zIndex: 200,
        background: "rgba(0,0,0,0.60)",
        backdropFilter: "blur(4px)",
        display: "grid", placeItems: "center",
        padding: 24,
        animation: "fadeIn 0.15s ease",
      }}
    >
      <style>{`
        @keyframes fadeIn { from { opacity:0; } to { opacity:1; } }
        @keyframes slideUp { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
      `}</style>

      <div style={{
        width: "100%", maxWidth: 420,
        background: "var(--surface)",
        borderRadius: 20,
        boxShadow: "0 40px 80px -30px rgba(0,0,0,0.7), inset 0 0 0 1px rgba(19,187,175,0.15)",
        padding: 28,
        animation: "slideUp 0.2s cubic-bezier(0.16,1,0.3,1)",
      }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 22 }}>
          <div>
            <h2 style={{ fontSize: 17, fontWeight: 600, letterSpacing: "-0.02em", color: "var(--ink)", margin: "0 0 3px" }}>
              Account settings
            </h2>
            <p style={{ fontSize: 12, color: "var(--muted)", margin: 0 }}>
              Update the name shown next to your profile
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              width: 30, height: 30, borderRadius: 8, border: "1px solid var(--border)",
              background: "var(--surface-2)", color: "var(--muted)",
              display: "grid", placeItems: "center", cursor: "pointer", flexShrink: 0,
            }}
            aria-label="Close"
          >
            <CloseIcon />
          </button>
        </div>

        {/* Avatar preview */}
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 24, padding: "14px 16px", borderRadius: 12, background: "var(--surface-2)", border: "1px solid var(--border)" }}>
          <div style={{
            width: 44, height: 44, borderRadius: "50%", flexShrink: 0,
            background: "linear-gradient(135deg, #13BBAF, #275A53)",
            display: "grid", placeItems: "center",
            color: "white", fontWeight: 700, fontSize: 18,
            boxShadow: "0 6px 16px -4px rgba(19,187,175,0.4)",
          }}>
            {firstName ? firstName[0].toUpperCase() : initial}
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)", marginBottom: 2 }}>
              {[firstName, lastName].filter(Boolean).join(" ") || "Your name"}
            </div>
            <div style={{ fontSize: 12, color: "var(--muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {user.email}
            </div>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, minWidth: 0 }}>
            <div style={{ minWidth: 0 }}>
              <label style={{ display: "block", fontSize: 12, fontWeight: 500, color: "var(--muted)", marginBottom: 6 }}>First name</label>
              <input
                type="text"
                value={firstName}
                onChange={(e) => { setFirstName(e.target.value); setSaved(false); setError(""); }}
                placeholder="Alex"
                autoComplete="given-name"
                autoFocus
                style={{
                  width: "100%", minWidth: 0, boxSizing: "border-box",
                  padding: "9px 12px", borderRadius: 10, fontSize: 14,
                  background: "var(--surface-2)", color: "var(--ink)",
                  border: "1px solid var(--border-strong)", outline: "none",
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = "rgba(19,187,175,0.5)")}
                onBlur={(e)  => (e.currentTarget.style.borderColor = "var(--border-strong)")}
              />
            </div>
            <div style={{ minWidth: 0 }}>
              <label style={{ display: "block", fontSize: 12, fontWeight: 500, color: "var(--muted)", marginBottom: 6 }}>Last name</label>
              <input
                type="text"
                value={lastName}
                onChange={(e) => { setLastName(e.target.value); setSaved(false); setError(""); }}
                placeholder="Morgan"
                autoComplete="family-name"
                style={{
                  width: "100%", minWidth: 0, boxSizing: "border-box",
                  padding: "9px 12px", borderRadius: 10, fontSize: 14,
                  background: "var(--surface-2)", color: "var(--ink)",
                  border: "1px solid var(--border-strong)", outline: "none",
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = "rgba(19,187,175,0.5)")}
                onBlur={(e)  => (e.currentTarget.style.borderColor = "var(--border-strong)")}
              />
            </div>
          </div>

          {error && (
            <p style={{ margin: 0, fontSize: 13, color: "var(--lo)", padding: "8px 12px", borderRadius: 8, background: "rgba(240,112,112,0.08)", border: "1px solid rgba(240,112,112,0.2)" }}>
              {error}
            </p>
          )}

          <div style={{ display: "flex", gap: 10, marginTop: 2 }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                flex: 1, padding: "10px 16px", borderRadius: 10, fontSize: 14, fontWeight: 500,
                background: "var(--surface-2)", color: "var(--ink-2)",
                border: "1px solid var(--border-strong)", cursor: "pointer",
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy || saved}
              style={{
                flex: 1, padding: "10px 16px", borderRadius: 10, fontSize: 14, fontWeight: 600,
                background: saved
                  ? "rgba(19,187,175,0.15)"
                  : "linear-gradient(135deg, #19D4C6 0%, #0EA89E 100%)",
                color: saved ? "#13BBAF" : "#020E0C",
                border: saved ? "1px solid rgba(19,187,175,0.3)" : "none",
                cursor: busy || saved ? "default" : "pointer",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                boxShadow: saved ? "none" : "0 6px 16px -4px rgba(19,187,175,0.35)",
                transition: "all 0.2s",
                opacity: busy ? 0.7 : 1,
              }}
            >
              {saved ? (<><CheckIcon /> Saved</>) : busy ? "Saving…" : "Save changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── User dropdown menu ────────────────────────────────────────────────────────

function UserMenu({
  user,
  onSignOut,
  onOpenSettings,
}: {
  user: { email: string | null; displayName?: string | null } | null;
  onSignOut: () => void;
  onOpenSettings: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const email = user?.email ?? "";
  const displayName = user?.displayName ?? "";
  const initial = (displayName || email || "?")[0].toUpperCase();

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          width: 34, height: 34, borderRadius: "50%",
          background: "linear-gradient(135deg, #13BBAF 0%, #275A53 100%)",
          display: "grid", placeItems: "center",
          color: "white", fontWeight: 700, fontSize: 13,
          border: open ? "2px solid rgba(19,187,175,0.7)" : "2px solid transparent",
          cursor: "pointer", transition: "border-color 0.2s",
          boxShadow: "0 6px 16px -4px rgba(19,187,175,0.4)",
        }}
        aria-label="User menu"
      >
        {initial}
      </button>

      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 10px)", right: 0,
          minWidth: 220, background: "var(--surface)", borderRadius: 14,
          boxShadow: "0 20px 60px -20px rgba(0,0,0,0.6), inset 0 0 0 1px var(--border-s)",
          padding: "6px", zIndex: 50,
          animation: "dropIn 0.18s cubic-bezier(0.16,1,0.3,1)",
        }}>
          <style>{`@keyframes dropIn { from { opacity:0; transform:translateY(-4px); } to { opacity:1; transform:translateY(0); } }`}</style>

          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", marginBottom: 4 }}>
            <div style={{
              width: 36, height: 36, borderRadius: "50%",
              background: "linear-gradient(135deg, #13BBAF, #275A53)",
              display: "grid", placeItems: "center",
              color: "white", fontWeight: 700, fontSize: 14, flexShrink: 0,
            }}>
              {initial}
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {displayName || email}
              </div>
              {displayName && (
                <div style={{ fontSize: 12, color: "var(--muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 160 }}>
                  {email}
                </div>
              )}
            </div>
          </div>

          <div style={{ height: 1, background: "var(--border)", margin: "4px 6px" }} />

          <button
            onClick={() => { setOpen(false); onOpenSettings(); }}
            style={{
              display: "flex", alignItems: "center", gap: 10,
              width: "100%", padding: "9px 12px",
              background: "none", border: "none", cursor: "pointer",
              fontSize: 13, color: "var(--ink-2)", borderRadius: 8, textAlign: "left",
              transition: "background 0.15s",
            }}
            onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "var(--surface-2)")}
            onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "none")}
          >
            <span style={{ display: "inline-flex", color: "var(--muted)" }}><UserMenuIcon /></span>
            Account settings
          </button>

          <button
            onClick={() => { setOpen(false); onSignOut(); }}
            style={{
              display: "flex", alignItems: "center", gap: 10,
              width: "100%", padding: "9px 12px",
              background: "none", border: "none", cursor: "pointer",
              fontSize: 13, color: "var(--lo)", borderRadius: 8, textAlign: "left",
              transition: "background 0.15s",
            }}
            onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "rgba(240,112,112,0.1)")}
            onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "none")}
          >
            <span style={{ display: "inline-flex" }}><LogoutIcon /></span>
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

// ── Navbar ────────────────────────────────────────────────────────────────────

export default function Navbar() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [settingsOpen, setSettingsOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    router.replace("/auth");
  };

  return (
    <>
      <header style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 40,
        background: "color-mix(in srgb, var(--bg) 80%, transparent)",
        backdropFilter: "saturate(180%) blur(20px)",
        WebkitBackdropFilter: "saturate(180%) blur(20px)",
        borderBottom: "1px solid var(--border)",
      }}>
        <div style={{
          maxWidth: 1240, margin: "0 auto", padding: "13px 32px",
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16,
        }}>
          {/* Logo */}
          <Link href="/" style={{
            display: "flex", alignItems: "center", gap: 10,
            fontWeight: 600, fontSize: 15, letterSpacing: "-0.01em",
            color: "var(--ink)", textDecoration: "none",
          }}>
            <FutureFCLogo />
            <span>FUTURE FC</span>
          </Link>

          {/* Right */}
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {user ? (
              <>
                <span
                  style={{ fontSize: 13, color: "var(--muted)", maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                  className="hidden sm:block"
                >
                  {user.displayName || user.email}
                </span>
                <UserMenu
                  user={user}
                  onSignOut={handleLogout}
                  onOpenSettings={() => setSettingsOpen(true)}
                />
              </>
            ) : (
              <Link href="/auth" className="btn-primary" style={{ padding: "9px 18px", fontSize: 14, borderRadius: 10 }}>
                Sign in
              </Link>
            )}
          </div>
        </div>
      </header>

      {settingsOpen && user && (
        <AccountSettingsModal
          user={user}
          onClose={() => setSettingsOpen(false)}
        />
      )}
    </>
  );
}
