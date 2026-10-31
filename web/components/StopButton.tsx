"use client";
import { useState } from "react";

/** The kill switch: pauses every campaign, ad set and ad this run created on Meta, after one confirmation. */
export default function StopButton({ runId, mode }: { runId: string; mode: "sandbox" | "live" }) {
  const [confirming, setConfirming] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; lines: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function stop(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const res = await fetch("/api/stop", {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ id: runId, mode, by: name }),
    });
    const body = await res.json().catch(() => ({}));
    if (res.status === 400 || res.status === 404 || res.status === 409) setError(body.error ?? "Something went wrong.");
    else setResult({ ok: Boolean(body.ok), lines: body.lines ?? [] });
    setBusy(false);
  }

  if (!confirming) {
    return <button type="button" className="btn secondary" onClick={() => setConfirming(true)}>Pause everything now</button>;
  }
  return (
    <form onSubmit={stop} className="stack" style={{ gap: 10 }} aria-label="Kill switch">
      <p className="small">Pause every campaign, ad set and ad this campaign created on the {mode === "live" ? "live account" : "sandbox"}.
        It takes a few seconds and is logged with your name.</p>
      <div className="row" style={{ gap: 10 }}>
        <input aria-label="Your name" placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)}
               className="btn secondary" style={{ height: 36, width: 200, textAlign: "left", cursor: "text", fontWeight: 400 }} />
        <button className="btn" disabled={busy || !name.trim()}>{busy ? "Pausing…" : "Pause everything"}</button>
        <button type="button" className="btn secondary" onClick={() => setConfirming(false)} disabled={busy}>Cancel</button>
      </div>
      {error && <p className="error-text small" role="alert">{error}</p>}
      {result && (
        <div role="status" className="stack small" style={{ gap: 4 }}>
          <span className={`tag ${result.ok ? "ok" : "bad"}`}>{result.ok ? "Everything paused" : "Some objects were not paused"}</span>
          {result.lines.slice(-8).map((l, i) => <span key={i} className="num muted">{l}</span>)}
        </div>
      )}
    </form>
  );
}
