"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { AgencyStep } from "@/lib/meta";
import type { RunView } from "@/lib/runs";
import { eur, fileUrl, usd } from "@/lib/format";
import StopButton from "./StopButton";

const STEP_LABEL = { connect: "Meta account checked", create: "Ads researched, made and tested", publish: "Campaign created on Meta" } as const;
const STATUS: Record<string, [string, string]> = {
  ok: ["ok", "done"], cached: ["ok", "done"], waiting: ["warn", "waiting for you"], skipped: ["neutral", "skipped"],
  error: ["bad", "failed"], start: ["sim", "working…"],
};
const LEVEL: Record<string, string> = { dry_run: "Prepare only: nothing is sent to Meta", propose: "Asks you before each action", autopilot: "Autopilot within your cap" };
const OBJECTIVE: Record<string, string> = { app_promotion: "App installs (App Store)", traffic: "Clicks to the app's website" };

/** The engine speaks to the CLI ("--landing-url"); the owner gets the same reason in the site's words. */
function plain(error: string): string {
  if (error.includes("not registered with Meta"))
    return "Meta refuses App Store links for clicks, and this app has no website on its App Store page. Start again with your website in the Website box (or connect the app's Meta app id): nothing was spent.";
  return error.replace(/^[A-Za-z]+Error: /, "").replace(/^connect: /, "");
}

function Status({ s }: { s: AgencyStep | null }) {
  if (!s) return <span className="tag neutral">not yet</span>;
  const [tag, text] = STATUS[s.status] ?? ["neutral", s.status];
  return <span className={`tag ${tag}`} title={s.error ?? undefined}>{text}</span>;
}

/** The agency on the owner's Meta account: what it did, what waits for them, every morning, the kill switch. */
export default function AgencyPanel({ run, onRefresh }: { run: RunView; onRefresh: () => Promise<void> }) {
  const a = run.agency!;
  const [name, setName] = useState("");
  const [at, setAt] = useState(a.schedule?.at || "08:00");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [following, setFollowing] = useState(0);
  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; }, []);

  // follow the engine while it works (it runs in the background): every 3 s, for at most 10 min after an action
  const working = a.running || following > 0;
  useEffect(() => {
    if (!working) return;
    const t = setInterval(() => {
      if (!document.hidden) void onRefresh();
      setFollowing((f) => Math.max(0, f - 1));
    }, 3000);
    return () => clearInterval(t);
  }, [working, onRefresh]);

  async function post(what: string, url: string, body: object): Promise<boolean> {
    setBusy(what);
    setError(null);
    try {
      const res = await fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.ok === false) { setError(data.error ?? "Something went wrong."); return false; }
      await onRefresh();
      return true;
    } catch {
      setError("Network error: nothing was confirmed.");
      return false;
    } finally {
      if (alive.current) setBusy(null);
    }
  }
  const resume = async (approvedBy?: string) => {
    if (await post(approvedBy ? "approve" : "resume", "/api/agency/resume", { id: run.id, approvedBy })) setFollowing(200);
  };

  const publish = a.steps.publish;
  const campaignUrl = typeof publish?.outputs.url === "string" ? publish.outputs.url : null;
  const onMeta = Boolean(publish?.outputs.campaign) || a.days.some((d) => Number(d.outputs.live ?? 0) + Number(d.outputs.new ?? 0) + Number(d.outputs.published_paused ?? 0) > 0);
  const failed = [a.steps.connect, a.steps.create, publish, a.days[0] ?? null].find((s) => s?.status === "error");

  return (
    <div className="card flush raised approve">
      <div className="stack" style={{ gap: 14 }}>
        <div className="spread">
          <h3>The agency</h3>
          <span className={`tag dot ${a.simulated ? "sim" : a.paused ? "neutral" : "ok"}`}>
            {a.simulated ? "Simulated account" : a.paused ? "On Meta, paused" : a.level === "dry_run" ? "Prepare only" : "On Meta"}
          </span>
        </div>
        {a.account ? (
          <p className="small muted">
            <strong>{a.account.accountName || a.account.act}</strong> · ads speak as {a.account.pageName ?? "no Page"}
            {a.account.daysLeft !== null && <> · login valid {Math.max(0, a.account.daysLeft)} more days</>}
          </p>
        ) : <p className="small muted">Simulated account: results are invented by a known model and labelled as such. <Link href="/connect">Connect Meta</Link></p>}
        <ul className="small stack" style={{ gap: 6, listStyle: "none", padding: 0, margin: 0 }}>
          <li>{a.paused ? "Test mode: everything is created PAUSED and never activated, nothing can spend" : LEVEL[a.level] ?? a.level}</li>
          <li>Cap {eur(a.dailyCapEur)}/day for everything{a.objective ? ` · ${OBJECTIVE[a.objective] ?? a.objective}` : ""}</li>
          {a.website && a.objective === "traffic" && <li className="muted">Ads link to {a.website}</li>}
        </ul>

        {a.waiting && (
          <form className="stack" style={{ gap: 10 }} onSubmit={(e) => { e.preventDefault(); void resume(name); }}>
            <p className="small"><strong>Waiting for your approval</strong> before anything goes to Meta{a.paused ? " (created paused)" : ""}.</p>
            <div className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
              <input aria-label="Your name" placeholder="Your name, to approve" value={name} onChange={(e) => setName(e.target.value)} className="input" style={{ flex: 1 }} />
              <button className="btn" disabled={busy !== null || working || !name.trim()}>{busy === "approve" ? "Starting…" : "Approve"}</button>
            </div>
          </form>
        )}
        {error && <p className="error-text small" role="alert">{error}</p>}
        {failed?.error && <p className="error-text small" role="alert">{plain(failed.error)}</p>}
      </div>

      <div className="stack" style={{ gap: 14 }}>
        <div className="spread">
          <h3>What it did</h3>
          {working ? <span className="tag sim"><span className="pulse-dot" aria-hidden /> working…</span> : <span className="small faint num">{usd(run.spentUsd)} AI</span>}
        </div>
        <ul className="stack small" style={{ gap: 8, listStyle: "none", padding: 0, margin: 0 }}>
          {(Object.keys(STEP_LABEL) as (keyof typeof STEP_LABEL)[]).map((k) => (
            <li key={k} className="spread"><span>{STEP_LABEL[k]}</span><Status s={a.steps[k]} /></li>
          ))}
          {a.days.slice(0, 5).map((d) => (
            <li key={d.day} className="spread" style={{ alignItems: "flex-start" }}>
              <span>
                Day {d.day}
                <span className="xsmall faint" style={{ display: "block" }}>
                  {d.outputs.simulated ? "simulated results · " : ""}{Number(d.outputs.live ?? 0)} live · {Number(d.outputs.new ?? 0)} new{Number(d.outputs.published_paused ?? 0) ? ` (${d.outputs.published_paused} on Meta, paused)` : ""}
                  {Number(d.outputs.paused ?? 0) ? ` · ${d.outputs.paused} paused` : ""}{Number(d.outputs.waiting_approval ?? 0) ? ` · ${d.outputs.waiting_approval} waiting` : ""}
                  {" · "}{eur(Number(d.outputs.committed_eur ?? 0))} of {eur(Number(d.outputs.cap_eur ?? a.dailyCapEur))}
                  {typeof d.outputs.report === "string" && <> · <a href={fileUrl(run.id, d.outputs.report)} target="_blank" rel="noreferrer">report</a></>}
                </span>
              </span>
              <Status s={d} />
            </li>
          ))}
        </ul>
        {campaignUrl && <a className="small" href={campaignUrl} target="_blank" rel="noreferrer">Open in Ads Manager →</a>}
        {a.log.some((l) => l.startsWith("✗")) && !working && <p className="error-text small">{a.log.filter((l) => l.startsWith("✗")).at(-1)?.slice(2)}</p>}

        <hr className="divider" />
        <div className="spread" style={{ gap: 10, flexWrap: "wrap" }}>
          <div>
            <h3 className="h4">Every morning</h3>
            <p className="xsmall faint">{a.schedule?.installed ? `Runs by itself at ${a.schedule.at}: results, pauses, new ads, report.`
              : a.schedule ? `Add this line to cron: runs at ${a.schedule.at}.` : "Reads results, pauses tired ads, ships new ones, writes the report."}</p>
          </div>
          <div className="row" style={{ gap: 8 }}>
            <input type="time" aria-label="Time of day" value={at} onChange={(e) => setAt(e.target.value)} className="input" style={{ width: 110 }} />
            <button type="button" className="btn secondary" disabled={busy !== null}
                    onClick={() => void post("schedule", "/api/agency/schedule", { id: run.id, at })}>
              {busy === "schedule" ? "Saving…" : a.schedule ? "Change" : "Set"}
            </button>
            {a.schedule && <button type="button" className="btn secondary" disabled={busy !== null}
                                   onClick={() => void post("unschedule", "/api/agency/schedule", { id: run.id, remove: true })}>Stop</button>}
          </div>
        </div>
        <div className="spread">
          <p className="xsmall faint">Or run today&apos;s day now (done days are never redone or re-billed).</p>
          <button type="button" className="btn secondary" disabled={busy !== null || working} onClick={() => void resume()}>
            {busy === "resume" ? "Starting…" : "Run today now"}
          </button>
        </div>
        {onMeta && a.account && <><hr className="divider" /><StopButton runId={run.id} mode={a.account.sandbox ? "sandbox" : "live"} endpoint="/api/agency/stop" /></>}
      </div>
    </div>
  );
}
