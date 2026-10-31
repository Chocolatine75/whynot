import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "whynot — your AI ad agency on Meta",
  description: "Research, strategy, ads tested before you spend, campaigns run within your budget.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <nav className="nav">
          <Link href="/" className="wordmark">whynot</Link>
          <div className="nav-links">
            <Link href="/#campaigns">Campaigns</Link>
            <Link href="/validation">Validation</Link>
            <Link href="/" className="btn compact">New campaign</Link>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
