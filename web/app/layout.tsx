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
          <Link href="/" className="wordmark">why<span>not</span></Link>
          <div className="row small">
            <Link href="/#campaigns" className="muted">Campaigns</Link>
            <Link href="/#new" className="btn" style={{ height: 32, padding: "0 14px", fontSize: 13 }}>New campaign</Link>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
