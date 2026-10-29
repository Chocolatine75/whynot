"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { runUrl } from "@/lib/format";

export default function NewCampaign() {
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
    const res = await fetch("/api/runs", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ app, countries, dailyCapEur: Number(cap) }),
    });
    const data = await res.json();
    if (!res.ok) { setError(data.error ?? "Something went wrong."); setBusy(false); return; }
    router.push(runUrl(data.id));
  }

  return (
    <form id="new" className="card raised new-campaign stack" onSubmit={submit} style={{ padding: 28 }}>
      <div className="field">
        <label className="label" htmlFor="app">Your app</label>
        <input id="app" className="input" placeholder="https://apps.apple.com/us/app/…" value={app}
               onChange={(e) => setApp(e.target.value)} required />
      </div>
      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <div className="field">
          <label className="label" htmlFor="countries">Where you advertise</label>
          <input id="countries" className="input" placeholder="US or FR GB" value={countries}
                 onChange={(e) => setCountries(e.target.value)} />
        </div>
        <div className="field">
          <label className="label" htmlFor="cap">Daily budget cap (€)</label>
          <input id="cap" className="input num" inputMode="decimal" value={cap} onChange={(e) => setCap(e.target.value)} />
        </div>
      </div>
      {error && <p className="error-text" role="alert">{error}</p>}
      <div className="row" style={{ justifyContent: "space-between" }}>
        <p className="small muted">Nothing is published or spent until you approve. AI cost for a full run: about $2–4.</p>
        <button className="btn large" disabled={busy || !app}>{busy ? "Starting…" : "Hand it to the agency"}</button>
      </div>
    </form>
  );
}
