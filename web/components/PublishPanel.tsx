"use client";
import { useEffect, useState } from "react";
import type { RunView } from "@/lib/runs";

interface Readiness { mode: "sandbox" | "live"; ready: boolean; missing: string[]; appInstalls: boolean }

const OUTCOME_TAG: Record<string, string> = { execute: "ok", needs_approval: "warn", simulated: "sim", refused: "bad" };

/** Approve and publish: sandbox by default; the engine applies the cap and approval rules again. */
export default function PublishPanel({ run, onRefresh }: { run: RunView; onRefresh: () => Promise<void> }) {
  const [ready, setReady] = useState<Readiness[] | null>(null);
  const [mode, setMode] = useState<"sandbox" | "live">("sandbox");
  const [objective, setObjective] = useState<"traffic" | "app_promotion">("traffic");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { fetch("/api/publish").then((r) => r.json()).then(setReady).catch(() => setReady([])); }, []);

  const pub = run.published;
  const current = ready?.find((r) => r.mode === mode);

  async function approve(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const res = await fetch("/api/publish", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ id: run.id, mode, objective, approvedBy: name }),
    });
    if (!res.ok) { setError((await res.json()).error ?? "Something went wrong."); setBusy(false); return; }
    for (let i = 0; i < 45; i++) {  // the engine runs in the background; follow it for up to 90 s
      await new Promise((r) => setTimeout(r, 2000));
      await onRefresh();
    }
    setBusy(false);
  }

  return (
    <div className="card raised stack" style={{ marginTop: 20, gap: 14 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h3>Approve and publish</h3>
        {pub && <span className={`tag ${pub.status === "published" || pub.status === "active" ? "ok" : pub.status === "refused" ? "warn" : "neutral"}`}>
          {pub.mode === "sandbox" ? "Sandbox" : "Live"} · {pub.status}</span>}
      </div>

      {pub && (
        <div className="stack" style={{ gap: 8 }}>
          <p className="small muted">
            {pub.mode === "sandbox" ? "Sandbox account: these objects never deliver and never spend." : "Live account."}
            {pub.approved_by && <> Approved by {pub.approved_by}.</>}
          </p>
          <div className="row" style={{ gap: 6 }}>
            {pub.decisions.map((d) => <span key={d.ad_set} className={`tag ${OUTCOME_TAG[d.outcome] ?? "neutral"}`} title={d.why}>{d.ad_set}: {d.outcome.replace("_", " ")}</span>)}
          </div>
          {Object.keys(pub.objects).length > 0 && (
            <p className="small num">
              Created on Meta: 1 campaign · {Object.keys(pub.objects).filter((k) => k.startsWith("adset_")).length} ad sets ·{" "}
              {Object.keys(pub.objects).filter((k) => k.startsWith("ad_")).length} ads — {pub.status === "active" ? "active" : "all paused"}
            </p>
          )}
          {pub.campaign_url && <a className="small" href={pub.campaign_url} target="_blank" rel="noreferrer">Open in Ads Manager →</a>}
        </div>
      )}
      {run.publishLog.some((l) => l.startsWith("✗")) && (
        <p className="error-text small">{run.publishLog.filter((l) => l.startsWith("✗")).at(-1)?.slice(2)}</p>
      )}

      <form onSubmit={approve} className="stack" style={{ gap: 12 }}>
        <div className="row" style={{ gap: 8 }}>
          <div className="tabs" style={{ position: "static", marginTop: 0 }} role="radiogroup" aria-label="Account">
            {(["sandbox", "live"] as const).map((m) => (
              <a key={m} role="radio" aria-checked={mode === m} href="#campaign" onClick={(e) => { e.preventDefault(); setMode(m); }}
                 style={mode === m ? { background: "var(--surface)", color: "var(--text)", boxShadow: "var(--shadow-1)" } : undefined}>
                {m === "sandbox" ? "Sandbox" : "Live account"}
              </a>
            ))}
          </div>
          <select aria-label="Objective" value={objective} onChange={(e) => setObjective(e.target.value as typeof objective)}
                  className="btn secondary" style={{ height: 34 }}>
            <option value="traffic">Clicks to the App Store</option>
            <option value="app_promotion" disabled={!current?.appInstalls}>App installs{current?.appInstalls ? "" : " (needs META_APP_ID)"}</option>
          </select>
        </div>
        {current && !current.ready && (
          <p className="small muted">To publish to the {mode === "sandbox" ? "sandbox" : "live account"}, add to <code>.env</code>: {current.missing.join(", ")}.</p>
        )}
        {mode === "live" && <p className="small muted">The live account follows your autonomy level and daily cap in <code>.env</code>; with the defaults (dry run, €0) nothing is created.</p>}
        <div className="row" style={{ gap: 10 }}>
          <input aria-label="Your name" placeholder="Your name, to approve" value={name} onChange={(e) => setName(e.target.value)}
                 className="btn secondary" style={{ height: 36, width: 220, textAlign: "left", cursor: "text", fontWeight: 400 }} />
          <button className="btn" disabled={busy || !current?.ready || !name.trim()}>
            {busy ? "Publishing…" : mode === "sandbox" ? "Approve and publish to sandbox" : "Approve and publish"}
          </button>
        </div>
        {error && <p className="error-text small" role="alert">{error}</p>}
        <p className="small muted">Everything is created paused. Activation is a separate step.</p>
      </form>
    </div>
  );
}
