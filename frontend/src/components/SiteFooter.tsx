import Link from "next/link";

const LINK_STYLE = { display: "inline-flex", alignItems: "center", minHeight: 24, color: "var(--primary-text)", textDecoration: "none", fontWeight: 600 };

/** Required attributions and legal links, shown on every page from the root layout. */
export default function SiteFooter() {
  return (
    <footer style={{ borderTop: "1px solid var(--border)", padding: "24px clamp(16px, 4vw, 32px) calc(24px + env(safe-area-inset-bottom, 0px))" }}>
      <div style={{
        maxWidth: 1200, margin: "0 auto",
        display: "flex", flexDirection: "column", gap: 6,
        fontSize: 12, lineHeight: 1.6, color: "var(--muted)",
      }}>
        <p style={{ margin: 0 }}>Football data provided by the Football-Data.org API</p>
        <p style={{ margin: 0 }}>Predictions generated with Google Gemini</p>
        <p style={{ margin: 0 }}>Not affiliated with any league or club; names are trademarks of their owners</p>
        <nav aria-label="Legal" style={{ display: "flex", gap: 16, marginTop: 6 }}>
          <Link href="/privacy" style={LINK_STYLE}>Privacy</Link>
          <Link href="/terms" style={LINK_STYLE}>Terms</Link>
        </nav>
      </div>
    </footer>
  );
}
