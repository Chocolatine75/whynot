import type { Metadata } from "next";
import Link from "next/link";
import AppIcon from "@/components/AppIcon";
import { Chevron } from "@/components/Icons";
import { STATUS_TAG, ago, runUrl, usd } from "@/lib/format";
import { listRuns } from "@/lib/runs";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Campaigns — whynot" };

export default function Campaigns() {
  const runs = listRuns();
  return (
    <main className="page narrow" id="content">
      <div className="page-head">
        <div>
          <h1>Campaigns</h1>
          <p>Every app the agency has worked on, newest first.</p>
        </div>
        <Link href="/" className="btn">New campaign</Link>
      </div>
      <div className="card flush spot">
        {runs.length === 0 ? <p className="empty">No campaign yet. Paste an App Store link on the home page to start one.</p> : (
          <div className="runs">
            {runs.map((r) => {
              const [kind, label] = STATUS_TAG[r.status];
              const what = [r.ads ? `${r.ads} ads` : "", r.videos ? `${r.videos} videos` : "", r.adSets ? `${r.adSets} audiences` : ""].filter(Boolean).join(" · ");
              return (
                <Link key={r.id} href={runUrl(r.id)} className="run-row">
                  <AppIcon run={r.id} icon={r.icon} name={r.appName} />
                  <div style={{ minWidth: 0 }}>
                    <div className="name">{r.appName}</div>
                    <div className="small muted">{ago(r.startedAt)}{what && ` · ${what}`}</div>
                  </div>
                  <span className="small muted num mono hide-sm">{usd(r.spentUsd)}</span>
                  <span className={`tag dot ${kind}`}>{label}</span>
                  <Chevron className="chev hide-sm" />
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}
