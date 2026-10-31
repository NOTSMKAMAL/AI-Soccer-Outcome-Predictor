"use client";

import type { ReactNode } from "react";
import Navbar from "@/components/Navbar";

export const CONTACT_EMAIL = "chrome.usa.llc@gmail.com";
export const LEGAL_LAST_UPDATED = "October 30, 2026";

/** Shared layout for the Privacy and Terms pages. */
export default function LegalPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div style={{ minHeight: "100vh" }}>
      <Navbar />
      <main style={{ maxWidth: 720, margin: "0 auto", padding: "104px clamp(16px, 4vw, 32px) 64px" }}>
        <h1 style={{
          fontSize: "clamp(30px, 6vw, 40px)", fontWeight: 700, letterSpacing: "-0.02em",
          color: "var(--ink)", margin: "0 0 6px", fontFamily: "var(--font-display), system-ui",
        }}>
          {title}
        </h1>
        <p style={{ fontSize: 13, color: "var(--muted)", margin: "0 0 32px" }}>
          Last updated: {LEGAL_LAST_UPDATED}
        </p>
        {children}
      </main>
    </div>
  );
}

export function LegalSection({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <section style={{ marginBottom: 28, fontSize: 15, lineHeight: 1.7, color: "var(--ink-2)" }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, color: "var(--ink)", margin: "0 0 8px" }}>{heading}</h2>
      {children}
    </section>
  );
}

export function ContactLink() {
  return <a href={`mailto:${CONTACT_EMAIL}`} style={{ color: "var(--accent-2)" }}>{CONTACT_EMAIL}</a>;
}
