"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { runUrl } from "@/lib/format";

/** The command bar: paste the App Store link, hand it to the agency (Muse-style input pill). */
export default function NewCampaign({ tone = "dark" }: { tone?: "dark" | "light" }) {
  const router = useRouter();
  const [app, setApp] = useState("");
  const [countries, setCountries] = useState("US");
  const [cap, setCap] = useState("20");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
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
    <form className={`command ${tone}`} onSubmit={submit} aria-label="Start a campaign">
      <div className="command-bar">
        <input aria-label="Your App Store link" className="command-input" placeholder="Paste your App Store link"
               value={app} onChange={(e) => setApp(e.target.value)} required autoComplete="off" spellCheck={false} />
        <button className="btn command-go" disabled={busy || !app}>
          {busy ? "Starting…" : "Hand it to the agency"}
          <span aria-hidden className="arrow-go">→</span>
        </button>
      </div>
      <div className="command-options">
        <label>Countries
          <input aria-label="Countries" value={countries} onChange={(e) => setCountries(e.target.value)} placeholder="US" />
        </label>
        <label>Daily cap €
          <input aria-label="Daily budget cap in euros" inputMode="decimal" value={cap} onChange={(e) => setCap(e.target.value)} />
        </label>
        <span>Nothing goes live until you approve.</span>
      </div>
      {error && <p className="command-error" role="alert">{error}</p>}
    </form>
  );
}
