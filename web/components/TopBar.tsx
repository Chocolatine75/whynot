"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Mark, Wordmark } from "@/components/Logo";

const LINKS = [["/runs", "Campaigns"], ["/validation", "Validation"]] as const;

/** The top bar. On the home page the logo lives in the centre of the page, so the bar keeps only the links. */
export default function TopBar() {
  const path = usePathname();
  const home = path === "/";
  return (
    <header className={`topbar${home ? " bare" : ""}`}>
      {!home && <Link href="/" className="brand" aria-label="whynot, home"><Mark size={26} /><Wordmark /></Link>}
      <nav className="topnav" aria-label="Main">
        {LINKS.map(([href, label]) => (
          <Link key={href} href={href} aria-current={path.startsWith(href) ? "page" : undefined}>{label}</Link>
        ))}
      </nav>
    </header>
  );
}
