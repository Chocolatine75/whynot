import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Figtree, Geist_Mono } from "next/font/google";
import TopBar from "@/components/TopBar";
import "./globals.css";

// Figtree for the product (close to Meta's Optimistic), Bricolage Grotesque only for the home page's name,
// Geist Mono for money and measures
const display = Bricolage_Grotesque({ subsets: ["latin"], weight: ["700", "800"], variable: "--font-display", display: "swap" });
const sans = Figtree({ subsets: ["latin"], weight: ["400", "500", "600", "700", "800"], variable: "--font-sans", display: "swap" });
const mono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });

export const metadata: Metadata = {
  title: "whynot — your AI ad agency on Meta",
  description: "Paste your app. whynot researches your market, makes your ads, tests them before you spend, and runs them within your cap.",
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = { themeColor: "#ffffff" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable}`}>
      <body>
        <a href="#content" className="skip">Skip to content</a>
        <TopBar />
        {children}
      </body>
    </html>
  );
}
