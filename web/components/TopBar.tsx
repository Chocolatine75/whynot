"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [["/runs", "Campaigns"], ["/validation", "Validation"]] as const;

/** The top bar: the brand, two destinations. Transparent on the home page, where only the search bar matters. */
export default function TopBar() {
  const path = usePathname();
  return (
    <header className={`topbar${path === "/" ? " bare" : ""}`}>
      <Link href="/" className="brand" aria-label="whynot, home"><span className="mark" aria-hidden />whynot</Link>
      <nav className="topnav" aria-label="Main">
        {LINKS.map(([href, label]) => (
          <Link key={href} href={href} aria-current={path.startsWith(href) ? "page" : undefined}>{label}</Link>
        ))}
      </nav>
    </header>
  );
}
