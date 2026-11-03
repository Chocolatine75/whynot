"use client";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useConnections } from "@/components/ConnectMeta";
import { ArrowUp, LinkIcon } from "@/components/Icons";
import { runUrl } from "@/lib/format";

const EXAMPLES = [
  ["Duolingo", "https://apps.apple.com/us/app/duolingo-language-lessons/id570060128"],
  ["Headspace", "https://apps.apple.com/us/app/headspace-meditation-sleep/id493145008"],
] as const;

/** How far the agency may go on the connected account (the engine enforces it again). */
const MODES = {
  paused: { label: "Test on Meta, paused", level: "autopilot", paused: true },
  dry_run: { label: "Prepare only", level: "dry_run", paused: false },
  propose: { label: "Ask me before each action", level: "propose", paused: false },
  autopilot: { label: "Autopilot within my cap", level: "autopilot", paused: false },
} as const;
type Mode = keyof typeof MODES;

/** The one thing on the home page: paste the App Store link, hand it to the agency. */
export default function SearchBar() {
  const router = useRouter();
  const [app, setApp] = useState("");
  const [countries, setCountries] = useState("US");
  const [cap, setCap] = useState("20");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<Mode>("paused");
  const [website, setWebsite] = useState("");
  const { connections } = useConnections();
  const account = connections.find((c) => c.canPublish && (c.daysLeft === null || c.daysLeft >= 0)) ?? null;
  const input = useRef<HTMLInputElement>(null);
  // focus on desktop only: on a phone it would open the keyboard over the page
  useEffect(() => { if (matchMedia("(pointer: fine)").matches) input.current?.focus({ preventScroll: true }); }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!app.trim()) { setError("Paste your App Store link first."); return; }
    setBusy(true);
    setError(null);
    try {
      // connected: the whole agency runs on the account; otherwise the ads are made and tested only
      const res = account
        ? await fetch("/api/agency", {
          method: "POST", headers: { "content-type": "application/json" },
          body: JSON.stringify({ app, countries, dailyCapEur: Number(cap), account: account.accountId,
            level: MODES[mode].level, paused: MODES[mode].paused, landingUrl: website.trim() || undefined }),
        })
        : await fetch("/api/runs", {
          method: "POST", headers: { "content-type": "application/json" },
          body: JSON.stringify({ app, countries, dailyCapEur: Number(cap) }),
        });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Something went wrong.");
      router.push(runUrl(data.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <form className="search" onSubmit={submit} aria-label="Start a campaign">
      <div className={`search-ring${app ? " filled" : ""}`}>
        <div className="search-box">
          <LinkIcon className="search-icon" />
          <input aria-label="Your App Store link" className="search-input" placeholder="Paste your App Store link"
                 value={app} onChange={(e) => setApp(e.target.value)} autoComplete="off" spellCheck={false} ref={input} />
          <button className="btn search-go magnetic" disabled={busy} aria-label={busy ? "Starting" : "Start the agency"}>
            <ArrowUp />
          </button>
        </div>
      </div>
      <div className="search-meta">
        <label className="chip"><span className="k">Ads for</span>
          <input aria-label="Countries, 2-letter codes" value={countries} onChange={(e) => setCountries(e.target.value.toUpperCase())} style={{ width: 30 }} />
        </label>
        <label className="chip"><span className="k">Cap €</span>
          <input aria-label="Daily budget cap in euros" inputMode="decimal" value={cap} onChange={(e) => setCap(e.target.value)} style={{ width: 30 }} />
          <span className="k">/day</span>
        </label>
        {account ? (
          <label className="chip" title={`${account.accountName} · ${account.act}`}><span className="k">On Meta</span>
            <select aria-label="What the agency may do on your Meta account" value={mode} onChange={(e) => setMode(e.target.value as Mode)}>
              {(Object.keys(MODES) as Mode[]).map((m) => <option key={m} value={m}>{MODES[m].label}</option>)}
            </select>
          </label>
        ) : <Link href="/connect" className="chip ghost">Connect Meta</Link>}
        {account && !account.appId && (
          // Meta refuses App Store links for clicks: without the app registered with Meta, ads go to its website
          <label className="chip" title="Where the ads send people. Empty: the website on the App Store page, if it has one.">
            <span className="k">Website</span>
            <input aria-label="Your app's website (where the ads link)" placeholder="https://… (optional)" value={website}
                   onChange={(e) => setWebsite(e.target.value)} inputMode="url" autoComplete="url" spellCheck={false} style={{ width: 150 }} />
          </label>
        )}
        {EXAMPLES.map(([name, url]) => (
          <button key={name} type="button" className="chip ghost" onClick={() => { setApp(url); setError(null); }}>Try {name}</button>
        ))}
      </div>
      {error && <p className="search-error" role="alert">{error}</p>}
      {busy && <p className="search-status" role="status">Starting the agency…</p>}
    </form>
  );
}
