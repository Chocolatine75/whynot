import Link from "next/link";
import NewCampaign from "@/components/NewCampaign";
import ProductWindow from "@/components/ProductWindow";
import { STATUS_TAG, ago, runUrl, usd } from "@/lib/format";
import { listRuns } from "@/lib/runs";

export const dynamic = "force-dynamic";

const HOW = [
  ["Research", "Reads your App Store page and reviews, then your competitors’ real ads in the Meta Ad Library."],
  ["Strategy", "Who to target and why they hesitate. Every objection is quoted word for word from a real source."],
  ["Ads", "Built from your real app screens, in each audience’s language. Only facts you already state."],
  ["Tested before you spend", "Shown to simulated viewers next to real competitor ads, then improved where they object. A placebo checks the test itself."],
  ["Campaign", "One ad set per audience, prepared paused on Meta, within your daily cap."],
];

const PROMISES = [
  ["Dry run by default", "Nothing is published until you switch it on."],
  ["A hard daily cap", "Budgets never go above the limit you set."],
  ["Every action logged", "What it did, why, and what it cost."],
];

export default function Home() {
  const runs = listRuns();
  return (
    <main>
      <section className="intro">
        <h1>Your ads, made and tested before you spend.</h1>
        <p className="sub">Paste your app. whynot researches your market, writes the ads, tests them against your competitors and prepares the campaign. You approve.</p>
        <NewCampaign />
      </section>

      <ProductWindow />

      <section className="how narrow">
        <h2>How it works</h2>
        <p className="lede">About fifteen minutes and a few dollars of AI, from your App Store link to a campaign ready to launch.</p>
        <div className="list">
          {HOW.map(([title, text], i) => (
            <div key={title} className="list-row">
              <span className="n">{i + 1}</span>
              <div><h3>{title}</h3><p>{text}</p></div>
            </div>
          ))}
        </div>
        <div className="promises">
          {PROMISES.map(([t, d]) => <div key={t} className="promise"><h3>{t}</h3><p>{d}</p></div>)}
        </div>
      </section>

      <section id="campaigns" className="campaigns narrow">
        <h2>Campaigns</h2>
        {runs.length === 0
          ? <p className="muted">No campaign yet.</p>
          : (
            <div className="list">
              {runs.map((r) => {
                const [kind, label] = STATUS_TAG[r.status];
                return (
                  <Link key={r.id} href={runUrl(r.id)} className="list-link">
                    <div>
                      <div style={{ fontWeight: 500 }}>{r.appName}</div>
                      <div className="small muted">{ago(r.startedAt)} · {r.adSets ? `${r.adSets} ad sets, ${r.ads} ads` : "in progress"}</div>
                    </div>
                    <span className="small muted num">{usd(r.spentUsd)}</span>
                    <span className={`tag ${kind}`}>{label}</span>
                  </Link>
                );
              })}
            </div>
          )}
      </section>
    </main>
  );
}
