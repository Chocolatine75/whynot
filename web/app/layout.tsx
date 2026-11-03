import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import TopBar from "@/components/TopBar";
import "./globals.css";

const sans = Geist({ subsets: ["latin"], variable: "--font-geist", display: "swap" });
const mono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono", display: "swap" });

export const metadata: Metadata = {
  title: "whynot — your AI ad agency on Meta",
  description: "Paste your app. whynot researches your market, makes your ads, tests them before you spend, and runs them within your cap.",
};

export const viewport: Viewport = {
  themeColor: [{ media: "(prefers-color-scheme: light)", color: "#f5f7fa" }, { media: "(prefers-color-scheme: dark)", color: "#0a0d11" }],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <TopBar />
        {children}
      </body>
    </html>
  );
}
