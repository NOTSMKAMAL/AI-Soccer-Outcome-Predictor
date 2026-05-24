import type { Metadata } from "next";
import { Barlow_Condensed, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const barlowCondensed = Barlow_Condensed({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800", "900"],
  variable: "--font-display",
  display: "swap",
});

const plusJakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Soccer AI Predictor",
  description: "AI-powered match outcome predictions for the world's top leagues",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`dark ${barlowCondensed.variable} ${plusJakarta.variable}`}>
      <body
        style={{ fontFamily: "var(--font-body), system-ui, sans-serif" }}
        className="bg-[#030C0A] text-white antialiased"
      >
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
