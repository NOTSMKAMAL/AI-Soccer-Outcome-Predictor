import type { Metadata, Viewport } from "next";
import { Barlow_Condensed, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import SiteFooter from "@/components/SiteFooter";

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
  title: "FUTURE FC",
  description: "AI-powered match predictions by FUTURE FC",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  interactiveWidget: "resizes-content",
  themeColor: "#02070A",
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
        className="antialiased"
      >
        <Providers>{children}</Providers>
        <SiteFooter />
      </body>
    </html>
  );
}
