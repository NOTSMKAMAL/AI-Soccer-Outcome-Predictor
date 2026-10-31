"use client";

import { useEffect, useRef, useState, type RefObject } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import DeleteAccountSection from "@/components/DeleteAccountSection";

// 13px padding above and below the 40px logo.
export const NAVBAR_HEIGHT = 66;

function FutureFCLogo() {
  return (
    <img
      src="/future-fc-logo.svg"
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
  const dialogRef = useRef<HTMLDialogElement>(null);

  // showModal makes the page behind inert, keeps focus inside and handles Escape.
  useEffect(() => {
    dialogRef.current?.showModal();
    dialogRef.current?.querySelector("input")?.focus();
  }, []);

  const close = () => dialogRef.current?.close();

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === dialogRef.current) close();
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = [firstName.trim(), lastName.trim()].filter(Boolean).join(" ");
    if (!name) { setError("First name is required."); return; }
    setBusy(true);
    setError("");
    try {
      await updateDisplayName(name);
      setSaved(true);
      setTimeout(close, 900);
    } catch {
      setError("Failed to update name. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const initial = (existing || user.email || "?")[0].toUpperCase();

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="account-settings-title"
      onClick={handleOverlayClick}
      onClose={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 200,
        width: "100%", height: "100%", maxWidth: "none", maxHeight: "none",
        margin: 0, border: 0, color: "inherit",
        background: "var(--scrim)",
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
        maxHeight: "calc(100dvh - 48px)", overflowY: "auto",
        background: "var(--surface)",
        borderRadius: 20,
        boxShadow: "inset 0 0 0 1px var(--border-s)",
        padding: 28,
        animation: "slideUp 0.2s cubic-bezier(0.16,1,0.3,1)",
      }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 22 }}>
          <div>
            <h2 id="account-settings-title" style={{ fontSize: 17, fontWeight: 600, letterSpacing: "-0.02em", color: "var(--ink)", margin: "0 0 3px" }}>
              Account settings
            </h2>
            <p style={{ fontSize: 12, color: "var(--muted)", margin: 0 }}>
              Update the name shown next to your profile
            </p>
          </div>
          <button
            onClick={close}
            style={{
              width: 30, height: 30, borderRadius: 8, border: "1px solid var(--border)",
              background: "var(--surface-2)", color: "var(--muted)",
              display: "grid", placeItems: "center", cursor: "pointer", flexShrink: 0,
            }}
            aria-label="Close account settings"
          >
            <CloseIcon />
          </button>
        </div>

        {/* Avatar preview */}
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 24, padding: "14px 16px", borderRadius: 12, background: "var(--surface-2)", border: "1px solid var(--border)" }}>
          <div style={{
            width: 44, height: 44, borderRadius: "50%", flexShrink: 0,
            background: "var(--orange-gradient)",
            display: "grid", placeItems: "center",
            color: "var(--on-accent)", fontWeight: 700, fontSize: 18,
          }}>
            {firstName ? firstName[0].toUpperCase() : initial}
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)", marginBottom: 2 }}>
              {[firstName, lastName].filter(Boolean).join(" ") || "Your name"}
            </div>
            <div style={{ fontSize: 12, color: "var(--muted)", overflowWrap: "anywhere" }}>
              {user.email}
            </div>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, minWidth: 0 }}>
            <div style={{ minWidth: 0 }}>
              <label htmlFor="account-first-name" style={{ display: "block", fontSize: 12, fontWeight: 500, color: "var(--muted)", marginBottom: 6 }}>First name</label>
              <input
                id="account-first-name"
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
                  border: "1px solid var(--border-strong)",
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = "var(--primary)")}
                onBlur={(e)  => (e.currentTarget.style.borderColor = "var(--border-strong)")}
              />
            </div>
            <div style={{ minWidth: 0 }}>
              <label htmlFor="account-last-name" style={{ display: "block", fontSize: 12, fontWeight: 500, color: "var(--muted)", marginBottom: 6 }}>Last name</label>
              <input
                id="account-last-name"
                type="text"
                value={lastName}
                onChange={(e) => { setLastName(e.target.value); setSaved(false); setError(""); }}
                placeholder="Morgan"
                autoComplete="family-name"
                style={{
                  width: "100%", minWidth: 0, boxSizing: "border-box",
                  padding: "9px 12px", borderRadius: 10, fontSize: 14,
                  background: "var(--surface-2)", color: "var(--ink)",
                  border: "1px solid var(--border-strong)",
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = "var(--primary)")}
                onBlur={(e)  => (e.currentTarget.style.borderColor = "var(--border-strong)")}
              />
            </div>
          </div>

          {error && (
            <p style={{ margin: 0, fontSize: 13, color: "var(--danger)", padding: "8px 12px", borderRadius: 8, background: "var(--danger-soft)", border: "1px solid var(--danger-edge)" }}>
              {error}
            </p>
          )}

          <div style={{ display: "flex", gap: 10, marginTop: 2 }}>
            <button
              type="button"
              onClick={close}
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
                  ? "var(--primary-soft)"
                  : "var(--primary)",
                color: saved ? "var(--primary-text)" : "var(--on-accent)",
                border: saved ? "1px solid var(--primary-edge)" : "none",
                cursor: busy || saved ? "default" : "pointer",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                transition: "all 0.2s",
                opacity: busy ? 0.7 : 1,
              }}
            >
              {saved ? (<><CheckIcon /> Saved</>) : busy ? "Saving…" : "Save changes"}
            </button>
          </div>
        </form>

        <DeleteAccountSection />
      </div>
    </dialog>
  );
}

// ── User dropdown menu ────────────────────────────────────────────────────────

function UserMenu({
  user,
  buttonRef,
  onSignOut,
  onOpenSettings,
}: {
  user: { email: string | null; displayName?: string | null } | null;
  buttonRef: RefObject<HTMLButtonElement>;
  onSignOut: () => void;
  onOpenSettings: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onPointer = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  const email = user?.email ?? "";
  const displayName = user?.displayName ?? "";
  const initial = (displayName || email || "?")[0].toUpperCase();

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        ref={buttonRef}
        onClick={() => setOpen((o) => !o)}
        style={{
          width: 34, height: 34, borderRadius: "50%",
          background: "var(--orange-gradient)",
          display: "grid", placeItems: "center",
          color: "var(--on-accent)", fontWeight: 700, fontSize: 13,
          border: open ? "2px solid var(--primary-edge)" : "2px solid transparent",
          cursor: "pointer", transition: "border-color 0.2s",
        }}
        aria-label="Account menu"
        aria-expanded={open}
      >
        {initial}
      </button>

      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 10px)", right: 0,
          width: 260, maxWidth: "calc(100vw - 32px)", background: "var(--surface)", borderRadius: 14,
          boxShadow: "inset 0 0 0 1px var(--border-s)",
          padding: "6px", zIndex: 50,
          animation: "dropIn 0.18s cubic-bezier(0.16,1,0.3,1)",
        }}>
          <style>{`@keyframes dropIn { from { opacity:0; transform:translateY(-4px); } to { opacity:1; transform:translateY(0); } }`}</style>

          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", marginBottom: 4 }}>
            <div style={{
              width: 36, height: 36, borderRadius: "50%",
              background: "var(--orange-gradient)",
              display: "grid", placeItems: "center",
              color: "var(--on-accent)", fontWeight: 700, fontSize: 14, flexShrink: 0,
            }}>
              {initial}
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)", overflowWrap: "anywhere" }}>
                {displayName || email}
              </div>
              {displayName && (
                <div style={{ fontSize: 12, color: "var(--muted)", overflowWrap: "anywhere" }}>
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
              fontSize: 13, color: "var(--danger)", borderRadius: 8, textAlign: "left",
              transition: "background 0.15s",
            }}
            onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "var(--danger-soft)")}
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
  const pathname = usePathname();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);

  const handleLogout = async () => {
    await logout();
    router.replace("/");
  };

  return (
    <>
      <header style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 40,
        backgroundImage: "var(--nav-bar)",
      }}>
        <div style={{
          maxWidth: 1240, margin: "0 auto", padding: "13px clamp(16px, 4vw, 32px)",
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16,
        }}>
          {/* Logo */}
          <Link href={user ? "/dashboard" : "/"} style={{
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
                {/* Nav links for authenticated users */}
                <nav style={{ display: "flex", alignItems: "center", gap: 4 }} className="hidden sm:flex">
                  <Link
                    href="/dashboard"
                    style={{
                      display: "inline-flex", alignItems: "center", gap: 4,
                      padding: "6px 12px", borderRadius: 8,
                      fontSize: 13, fontWeight: 600, textDecoration: "none",
                      color: "var(--ink)",
                      background: pathname === "/dashboard" ? "var(--surface-2)" : "transparent",
                      transition: "color 0.15s, background 0.15s",
                    }}
                    onMouseEnter={(e) => { if (pathname !== "/dashboard") (e.currentTarget as HTMLAnchorElement).style.textDecoration = "underline"; }}
                    onMouseLeave={(e) => { if (pathname !== "/dashboard") (e.currentTarget as HTMLAnchorElement).style.textDecoration = "none"; }}
                  >
                    Fixtures
                  </Link>
                </nav>
                <UserMenu
                  user={user}
                  buttonRef={menuButtonRef}
                  onSignOut={handleLogout}
                  onOpenSettings={() => setSettingsOpen(true)}
                />
              </>
            ) : (
              <Link href="/auth" replace className="btn-primary" style={{ padding: "9px 18px", fontSize: 14, borderRadius: 10, background: "var(--orange-gradient)" }}>
                Sign in
              </Link>
            )}
          </div>
        </div>
      </header>

      {settingsOpen && user && (
        <AccountSettingsModal
          user={user}
          onClose={() => { setSettingsOpen(false); menuButtonRef.current?.focus(); }}
        />
      )}
    </>
  );
}
