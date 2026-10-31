import type { Metadata } from "next";
import Link from "next/link";
import LegalPage, { ContactLink, LegalSection } from "@/components/LegalPage";

export const metadata: Metadata = { title: "Terms · FUTURE FC" };

export default function TermsPage() {
  return (
    <LegalPage title="Terms">
      <LegalSection heading="About these terms">
        <p>
          FUTURE FC is a public, non-commercial portfolio project. By creating an account or using
          the site you agree to these terms. You must be at least 13 to use it. Our{" "}
          <Link href="/privacy" style={{ color: "var(--accent-2)" }}>Privacy Policy</Link> explains
          how data is handled.
        </p>
      </LegalSection>

      <LegalSection heading="Entertainment only">
        <p>
          Predictions are for entertainment only. Nothing on this site is betting advice or
          financial advice. Don&apos;t rely on it to place a bet or make any financial decision.
        </p>
      </LegalSection>

      <LegalSection heading="No guarantee of accuracy">
        <p>
          We don&apos;t guarantee that any prediction, statistic or fixture is accurate, complete or
          up to date. Football is unpredictable, and predictions are often wrong.
        </p>
      </LegalSection>

      <LegalSection heading="AI-generated content">
        <p>
          Prediction explanations are written by AI and may contain mistakes, including about teams
          and players. Check anything that matters to you.
        </p>
      </LegalSection>

      <LegalSection heading="Daily limits">
        <p>
          Predictions are limited each day, per account and across the site. Don&apos;t create extra
          accounts or use any other method to get around these limits.
        </p>
      </LegalSection>

      <LegalSection heading="Your account">
        <p>
          Keep your sign-in details safe. We may suspend or delete accounts that break these terms
          or misuse the site. You can delete your account at any time from Account settings.
        </p>
      </LegalSection>

      <LegalSection heading="Provided as-is">
        <p>
          The site is provided as-is and as available, with no warranties of any kind. It may change
          or stop at any time. To the extent the law allows, we aren&apos;t liable for any loss that
          comes from using it, including any loss from relying on a prediction.
        </p>
      </LegalSection>

      <LegalSection heading="Names and data">
        <p>
          Football data is provided by the Football-Data.org API. This site isn&apos;t affiliated with
          any league or club, and their names are trademarks of their owners.
        </p>
      </LegalSection>

      <LegalSection heading="Governing law">
        <p>These terms are governed by the laws of the State of California.</p>
      </LegalSection>

      <LegalSection heading="Contact">
        <p>Questions: <ContactLink /></p>
      </LegalSection>
    </LegalPage>
  );
}
