import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AI Sports Predictor",
  description: "AI-powered match outcome predictions for the world's top leagues",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-[#05050a] text-white antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
