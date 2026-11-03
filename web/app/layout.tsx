import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Figtree, Geist_Mono } from "next/font/google";
import Interactions from "@/components/Interactions";
import TopBar from "@/components/TopBar";
import "./globals.css";

// Bricolage Grotesque for titles (a face people remember), Figtree for reading (close to Meta's Optimistic),
// Geist Mono for money and measures
const display = Bricolage_Grotesque({ subsets: ["latin"], weight: ["500", "600", "700", "800"], variable: "--font-display", display: "swap" });
const sans = Figtree({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-sans", display: "swap" });
const mono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });

export const metadata: Metadata = {
  title: "whynot — your AI ad agency on Meta",
  description: "Paste your app. whynot researches your market, makes your ads, tests them before you spend, and runs them within your cap.",
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = { themeColor: "#05070d", colorScheme: "dark" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable}`}>
      <body>
        <div className="backdrop" aria-hidden><i className="b1" /><i className="b2" /><i className="b3" /><i className="spotlight" /><i className="grain" /></div>
        <a href="#content" className="skip">Skip to content</a>
        <TopBar />
        {children}
        <Interactions />
      </body>
    </html>
  );
}
