import type { Metadata } from "next";
import LegalPage, { ContactLink, LegalSection } from "@/components/LegalPage";

export const metadata: Metadata = { title: "Privacy Policy · FUTURE FC" };

const CELL = { padding: "10px 12px", borderTop: "1px solid var(--border)", textAlign: "left" as const, verticalAlign: "top" as const };

const AFTER_DELETION: Array<[string, string]> = [
  ["Your Firebase account (email, name, password or Google link)", "Deleted"],
  ["Your daily prediction counters, on every stored day", "Deleted"],
  ["Daily totals for the whole site", "Kept. These are plain numbers with no user ID or email"],
  ["Prediction history", "Kept. It never records who asked for a prediction"],
  ["Hosting request logs", "Kept for as long as the host retains them. They can include IP addresses"],
  ["Google's own Firebase backups and logs", "Governed by Google's retention terms, not by us"],
];

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy">
      <LegalSection heading="About this site">
        <p>
          FUTURE FC is a public, non-commercial portfolio project that predicts football match
          outcomes. It shows no ads, uses no analytics or tracking tools, and does not sell personal
          information. This policy describes what the site actually collects.
        </p>
      </LegalSection>

      <LegalSection heading="What we collect">
        <ul style={{ paddingLeft: 20, margin: 0 }}>
          <li>
            <strong>Account details.</strong> Your email address, your name if you give one, whether
            your email is verified, and sign-in times, held by Firebase Authentication. If you use
            email sign-in, Firebase stores your password in protected form and we never see it. If
            you use Google sign-in, Firebase also receives your basic Google profile.
          </li>
          <li>
            <strong>Daily prediction counters.</strong> How many predictions your account made each
            day, stored against your Firebase user ID. We use these to enforce daily limits.
          </li>
          <li>
            <strong>Sign-in tokens.</strong> Your browser sends a Firebase token with signed-in
            requests so the server can identify you. The server checks it and doesn&apos;t store it.
          </li>
          <li>
            <strong>Request logs.</strong> Our hosting providers record requests to the site. These
            logs can include IP addresses. We try to keep user IDs and email addresses out of our
            own server logs.
          </li>
        </ul>
        <p style={{ marginTop: 12 }}>
          Prediction history is stored too, but it holds only matches, probabilities and results. It
          never records who asked for a prediction.
        </p>
      </LegalSection>

      <LegalSection heading="Services that handle data">
        <ul style={{ paddingLeft: 20, margin: 0 }}>
          <li><strong>Firebase Authentication (Google):</strong> accounts and sign-in.</li>
          <li><strong>Cloud Firestore (Google):</strong> daily prediction counters and daily totals.</li>
          <li><strong>Google Gemini:</strong> writes the prediction explanations.</li>
          <li><strong>Vercel:</strong> hosts the website.</li>
          <li><strong>Render:</strong> hosts the server.</li>
        </ul>
        <p style={{ marginTop: 12 }}>
          Match data comes from football-data.org. Our server requests it; your personal information
          isn&apos;t sent to them.
        </p>
      </LegalSection>

      <LegalSection heading="Gemini">
        <p>
          We use Gemini&apos;s free tier, and Google may use what is sent to it to improve its
          products. We send only match information: team names, match statistics and the names of
          each league&apos;s top scorers. Your name, email address, user ID and IP address are not
          included.
        </p>
      </LegalSection>

      <LegalSection heading="Browser storage">
        <p>
          Firebase keeps you signed in using your browser&apos;s IndexedDB storage. The site itself
          sets no cookies and uses no advertising or analytics storage. If you choose Google
          sign-in, Google&apos;s own sign-in window may use its own cookies.
        </p>
      </LegalSection>

      <LegalSection heading="How long data is kept">
        <p>
          Your account and daily counters are kept until you delete your account. Request logs are
          kept for as long as each hosting provider retains them.
        </p>
      </LegalSection>

      <LegalSection heading="Deleting your account">
        <p>
          Sign in, open the menu at the top right, choose <strong>Account settings</strong>, then{" "}
          <strong>Delete account</strong>. You may be asked to sign in again first. Deletion is
          permanent. If you can&apos;t sign in, email us and we&apos;ll help.
        </p>
        <div style={{ overflowX: "auto", marginTop: 12 }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr>
                <th style={{ ...CELL, borderTop: "none" }}>Data</th>
                <th style={{ ...CELL, borderTop: "none" }}>After you delete your account</th>
              </tr>
            </thead>
            <tbody>
              {AFTER_DELETION.map(([data, outcome]) => (
                <tr key={data}>
                  <td style={CELL}>{data}</td>
                  <td style={CELL}>{outcome}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </LegalSection>

      <LegalSection heading="Children">
        <p>
          This site is not for anyone under 13, and we don&apos;t knowingly collect their
          information. If you believe a child under 13 has created an account, contact us and
          we&apos;ll delete it.
        </p>
      </LegalSection>

      <LegalSection heading="Changes to this policy">
        <p>If this policy changes, we&apos;ll update it here and change the date at the top.</p>
      </LegalSection>

      <LegalSection heading="Contact">
        <p>Questions or requests: <ContactLink /></p>
      </LegalSection>
    </LegalPage>
  );
}
