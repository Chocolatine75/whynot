"use client";
import { useEffect, useRef, useState } from "react";
import type { RunView } from "@/lib/runs";
import StopButton from "./StopButton";

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

  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; }, []);
  useEffect(() => { fetch("/api/publish").then((r) => r.json()).then(setReady).catch(() => setReady([])); }, []);

  const pub = run.published;
  const current = ready?.find((r) => r.mode === mode);
  const created = pub ? Object.keys(pub.objects) : [];
  // an install campaign needs the app's Meta id on this account: fall back to clicks when it isn't there
  useEffect(() => { if (objective === "app_promotion" && !current?.appInstalls) setObjective("traffic"); }, [current, objective]);

  async function approve(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/publish", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ id: run.id, mode, objective, approvedBy: name }),
      });
      if (!res.ok) { setError((await res.json().catch(() => ({}))).error ?? "Something went wrong."); return; }
      for (let i = 0; i < 45 && alive.current; i++) {  // the engine runs in the background; follow it for up to 90 s
        await new Promise((r) => setTimeout(r, 2000));
        await onRefresh();
      }
    } catch {
      setError("Network error.");
    } finally {
      if (alive.current) setBusy(false);
    }
  }

  return (
    <div className="card flush raised approve">
      <form onSubmit={approve} className="stack" style={{ gap: 14 }}>
        <h3>Approve</h3>
        <div className="seg" role="group" aria-label="Account">
          {(["sandbox", "live"] as const).map((m) => (
            <button key={m} type="button" aria-pressed={mode === m} onClick={() => setMode(m)}>
              {m === "sandbox" ? "Sandbox" : "Live account"}
            </button>
          ))}
        </div>
        <label className="stack small" style={{ gap: 6 }}>
          <span className="faint">Objective</span>
          <select aria-label="Objective" value={objective} onChange={(e) => setObjective(e.target.value as typeof objective)} className="select">
            <option value="traffic">Clicks to the App Store</option>
            <option value="app_promotion" disabled={!current?.appInstalls}>App installs{current?.appInstalls ? "" : " (needs META_APP_ID)"}</option>
          </select>
        </label>
        {current && !current.ready && (
          <p className="small muted">Connect your Meta {mode === "sandbox" ? "sandbox" : "ad account"} first (missing: {current.missing.join(", ")}).</p>
        )}
        <div className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
          <input aria-label="Your name" placeholder="Your name, to approve" value={name} onChange={(e) => setName(e.target.value)} className="input" style={{ flex: 1 }} />
          <button className="btn" disabled={busy || !current?.ready || !name.trim()}>
            {busy ? "Creating…" : "Approve and create (paused)"}
          </button>
        </div>
        {error && <p className="error-text small" role="alert">{error}</p>}
      </form>

      <div className="stack" style={{ gap: 14 }}>
        <div className="spread">
          <h3>On Meta</h3>
          {pub ? <span className={`tag dot ${pub.status === "published" || pub.status === "active" ? "ok" : pub.status === "refused" ? "warn" : "neutral"}`}>
            {pub.mode === "sandbox" ? "Sandbox" : "Live"} · {pub.status}</span> : <span className="tag neutral">Not published</span>}
        </div>
        {!pub ? <p className="small muted">Nothing created yet. After your approval, the campaign, its ad sets and ads appear here.</p> : (
          <>
            <p className="small muted">
              {pub.mode === "sandbox" ? "Sandbox account: these objects never deliver and never spend." : "Your ad account."}
              {pub.approved_by && <> Approved by {pub.approved_by}.</>}
            </p>
            {created.length > 0 && (
              <p className="small num">1 campaign · {created.filter((k) => k.startsWith("adset_")).length} ad sets · {created.filter((k) => k.startsWith("ad_")).length} ads · {pub.status === "active" ? "active" : "all paused"}</p>
            )}
            <div className="row" style={{ gap: 6 }}>
              {pub.decisions.map((d) => <span key={d.ad_set} className={`tag ${OUTCOME_TAG[d.outcome] ?? "neutral"}`} title={d.why}>{d.ad_set}: {d.outcome.replace("_", " ")}</span>)}
            </div>
            {pub.campaign_url && <a className="small" href={pub.campaign_url} target="_blank" rel="noreferrer">Open in Ads Manager →</a>}
          </>
        )}
        {run.publishLog.some((l) => l.startsWith("✗")) && (
          <p className="error-text small">{run.publishLog.filter((l) => l.startsWith("✗")).at(-1)?.slice(2)}</p>
        )}
        {pub && created.length > 0 && <><hr className="divider" /><StopButton runId={run.id} mode={pub.mode} /></>}
      </div>
    </div>
  );
}
