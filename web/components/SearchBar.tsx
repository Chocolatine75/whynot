"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowUp, LinkIcon } from "@/components/Icons";
import { runUrl } from "@/lib/format";

const EXAMPLES = [
  ["WhatsApp", "https://apps.apple.com/us/app/whatsapp-messenger/id310633997"],
  ["Duolingo", "https://apps.apple.com/us/app/duolingo-language-lessons/id570060128"],
  ["Headspace", "https://apps.apple.com/us/app/headspace-meditation-sleep/id493145008"],
] as const;

/** The one thing on the home page: paste the App Store link, hand it to the agency. */
export default function SearchBar() {
  const router = useRouter();
  const [app, setApp] = useState("");
  const [countries, setCountries] = useState("US");
  const [cap, setCap] = useState("20");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!app.trim()) { setError("Paste your App Store link first."); return; }
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/runs", {
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
                 value={app} onChange={(e) => setApp(e.target.value)} autoComplete="off" spellCheck={false} autoFocus />
          <button className="btn search-go" disabled={busy} aria-label={busy ? "Starting" : "Start the agency"}>
            <ArrowUp />
          </button>
        </div>
      </div>
      <div className="search-meta">
        <label className="chip"><span className="k">Countries</span>
          <input aria-label="Countries, 2-letter codes" value={countries} onChange={(e) => setCountries(e.target.value.toUpperCase())} />
        </label>
        <label className="chip"><span className="k">Daily cap €</span>
          <input aria-label="Daily budget cap in euros" inputMode="decimal" value={cap} onChange={(e) => setCap(e.target.value)} style={{ width: 36 }} />
        </label>
        <span className="faint small" aria-hidden>·</span>
        {EXAMPLES.map(([name, url]) => (
          <button key={name} type="button" className="chip" onClick={() => { setApp(url); setError(null); }}>Try {name}</button>
        ))}
      </div>
      {error && <p className="search-error" role="alert">{error}</p>}
      {busy && <p className="fineprint" role="status">Starting the agency…</p>}
    </form>
  );
}
