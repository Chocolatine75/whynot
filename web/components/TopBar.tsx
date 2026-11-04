"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Mark, Wordmark } from "@/components/Logo";

const DEMO = process.env.NEXT_PUBLIC_WHYNOT_DEMO === "1";

const LINKS = [["/runs", "Dashboard"], ["/validation", "Validation"], ["/connect", "Meta account"]] as const;

/** The top bar. On the dark landing page the name sits in the centre, so the bar keeps only the links. */
export default function TopBar() {
  const path = usePathname();
  const home = path === "/";
  return (
    <header className={`topbar${home ? " bare" : ""}`}>
      {!home && <Link href="/" className="brand" aria-label="whynot, home"><Mark size={26} /><Wordmark /></Link>}
      <nav className="topnav" aria-label="Main">
        {DEMO && !home && (
          <span className="tag sim" title="Read-only demo: the example run we made on Duolingo (its week of results is simulated) and our VietBuddy campaign. To run whynot on your own app, run it locally and connect your Meta account and your Meta AI keys.">
            Demo · example run
          </span>
        )}
        {LINKS.map(([href, label]) => (
          <Link key={href} href={href} aria-current={path.startsWith(href) ? "page" : undefined}>{label}</Link>
        ))}
      </nav>
    </header>
  );
}
