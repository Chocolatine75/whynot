import Link from "next/link";
import NewCampaign from "@/components/NewCampaign";
import { STATUS_TAG, ago, runUrl, usd } from "@/lib/format";
import { listRuns } from "@/lib/runs";

export const dynamic = "force-dynamic";

const STEPS = [
  ["Research", "Your App Store page, your reviews, and your competitors' real ads in the Meta Ad Library."],
  ["Strategy", "Who to target and why they hesitate — every claim backed by a real quote."],
  ["Ads, tested first", "Ads built from your real screens, tested in a simulated feed next to competitors, then improved."],
  ["Campaign", "A ready-to-launch Meta campaign within your budget. You approve, the agency runs it."],
];

export default function Home() {
  const runs = listRuns();
  return (
    <main className="page">
      <section className="hero">
        <p className="tag info" style={{ marginBottom: 20 }}>Built on Meta&apos;s Muse models</p>
        <h1>Your ad agency on Meta. Without the agency.</h1>
        <p>Paste your app. whynot researches your market, writes the strategy, makes the ads, tests them before you spend a cent, and runs the campaign within your budget.</p>
        <NewCampaign />
      </section>

      <section className="section grid grid-3" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))" }}>
        {STEPS.map(([title, text], i) => (
          <div key={title} className="card stack" style={{ gap: 8 }}>
            <span className="label num">0{i + 1}</span>
            <h3>{title}</h3>
            <p className="muted" style={{ fontSize: 15 }}>{text}</p>
          </div>
        ))}
      </section>

      <section id="campaigns" className="section">
        <h2>Campaigns</h2>
        <p className="lede">Every run keeps its research, ads and plan, so you can come back to it.</p>
        {runs.length === 0 && <p className="muted">No campaign yet.</p>}
        <div className="stack" style={{ gap: 4 }}>
          {runs.map((r) => {
            const [kind, label] = STATUS_TAG[r.status];
            return (
              <Link key={r.id} href={runUrl(r.id)} className="list-link">
                <div>
                  <div style={{ fontWeight: 600 }}>{r.appName}</div>
                  <div className="small muted">{ago(r.startedAt)} · {r.adSets ? `${r.adSets} ad sets, ${r.ads} ads` : "in progress"}</div>
                </div>
                <span className="small muted num">{usd(r.spentUsd)} AI</span>
                <span className={`tag ${kind}`}>{label}</span>
              </Link>
            );
          })}
        </div>
      </section>
    </main>
  );
}
