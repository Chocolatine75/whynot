import Link from "next/link";
import HeroDemo from "@/components/HeroDemo";
import NewCampaign from "@/components/NewCampaign";
import { STATUS_TAG, ago, runUrl, usd } from "@/lib/format";
import { listRuns } from "@/lib/runs";

export const dynamic = "force-dynamic";

const FEATURES = [
  {
    eyebrow: "Research",
    title: "It reads your market like an analyst would.",
    text: "Your App Store page and reviews, then your competitors’ real ads in the Meta Ad Library — who runs what, for how long, to whom. Spam and unrelated advertisers are filtered out.",
    visual: "research",
  },
  {
    eyebrow: "Strategy",
    title: "Every claim comes with a receipt.",
    text: "Who to target, why they hesitate and how to answer — each objection quoted word for word from a real review or ad, and checked by code. Ads may only state facts you already state.",
    visual: "strategy",
  },
  {
    eyebrow: "Tested before you spend",
    title: "Ads judged next to your competitors, before a cent goes out.",
    text: "Built from your real screens, then shown to simulated viewers in a feed next to real competitor ads. A placebo — a competitor ad wearing your name — tells you when the test itself is fooling you.",
    visual: "test",
  },
  {
    eyebrow: "Runs within your cap",
    title: "A campaign that waits for your yes.",
    text: "One ad set per audience, in its language, prepared paused on Meta. Your daily cap is a hard limit. The first launch always needs your approval, and every action is logged.",
    visual: "campaign",
  },
];

function FeatureVisual({ kind }: { kind: string }) {
  if (kind === "research")
    return (
      <div className="fv">
        {[["Rival Lingo", "running 181 days", "ok"], ["Other App", "stopped after 3 days", "neutral"], ["Win a free iPhone", "ignored: unrelated", "bad"]].map(([n, s, t]) => (
          <div key={n} className="fv-row"><b>{n}</b><span className={`tag ${t}`}>{s}</span></div>
        ))}
      </div>
    );
  if (kind === "strategy")
    return (
      <div className="fv">
        <h4>“It won’t hear me correctly.”</h4>
        <blockquote className="quote">“The app doesn’t hear you correctly.”<cite>review · 2★</cite></blockquote>
        <p className="small muted">Answer: lead with listening — train your ear before you speak.</p>
      </div>
    );
  if (kind === "test")
    return (
      <div className="fv">
        {[["Your ad · v2", "+1.8", "ok"], ["Your ad · v1", "+0.6", "neutral"], ["Placebo", "0.0", "sim"]].map(([n, s, t]) => (
          <div key={n} className="fv-row"><b>{n}</b><span className={`tag ${t} num`}>{s} vs competitor</span></div>
        ))}
        <p className="small muted">Simulated · placebo-checked</p>
      </div>
    );
  return (
    <div className="fv">
      {[["Profile 1 · US · 25–44", "€6.66"], ["Profile 2 · US · 25–54", "€6.66"], ["Profile 3 · US · 18–34", "€6.66"]].map(([n, b]) => (
        <div key={n} className="fv-row"><b>{n}</b><span className="num">{b}/day</span></div>
      ))}
      <div className="fv-meter"><span style={{ width: "99.9%" }} /></div>
      <div className="fv-row"><span className="small muted">€19.98 of your €20 cap</span><span className="tag warn">Waiting for your approval</span></div>
    </div>
  );
}

export default function Home() {
  const runs = listRuns();
  return (
    <main>
      <section className="hero-dark">
        <div className="hero-grid" aria-hidden />
        <div className="hero-inner">
          <p className="hero-proof"><span className="dot-live" />Built on Meta’s Muse models · Ad Library · Marketing API</p>
          <h1 className="hero-title">Your ads, made <span className="grad">and tested</span><br />before you spend.</h1>
          <p className="hero-sub">Paste your app. whynot researches your market, writes the strategy, makes the ads, tests them next to your competitors, and runs the campaign within your budget. You approve; it does the rest.</p>
          <NewCampaign tone="dark" />
          <HeroDemo />
        </div>
      </section>

      <section className="results-card page-narrow">
        {[["3 real apps", "language, wellbeing, travel — end to end"], ["$1–3", "of AI per campaign, measured on those 3"],
          ["100%", "of quotes checked word for word against their source"], ["€0 live", "until you approve and set a cap"]].map(([v, l]) => (
          <div key={v} className="result"><span className="result-value">{v}</span><span className="small muted">{l}</span></div>
        ))}
      </section>

      <div className="page">
        {FEATURES.map((f, i) => (
          <section key={f.eyebrow} className={`feature ${i % 2 ? "flip" : ""}`}>
            <div className="feature-text">
              <span className="eyebrow">{f.eyebrow}</span>
              <h2>{f.title}</h2>
              <p className="muted">{f.text}</p>
            </div>
            <div className="feature-visual"><span className="illustration">Illustration</span><FeatureVisual kind={f.visual} /></div>
          </section>
        ))}

        <section className="control">
          <span className="eyebrow">You stay in control</span>
          <h2>An agency that asks before it spends.</h2>
          <div className="grid grid-3" style={{ marginTop: 32 }}>
            {[["Dry run by default", "Everything is prepared, nothing is published, until you switch it on."],
              ["A hard daily cap", "Budgets can go down any time; they never go above the cap you set."],
              ["Every action logged", "What it did, why, and what it cost — in plain language."]].map(([t, d]) => (
              <div key={t} className="card stack" style={{ gap: 8 }}><h3>{t}</h3><p className="muted" style={{ fontSize: 15 }}>{d}</p></div>
            ))}
          </div>
        </section>

        <section id="campaigns" className="section">
          <h2>Your campaigns</h2>
          <p className="lede">Each one keeps its research, ads and plan, so you can come back to it.</p>
          {runs.length === 0 && <p className="muted">No campaign yet — paste your app above.</p>}
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

        <section id="new" className="final-cta">
          <h2>Hand your ads to the agency.</h2>
          <p className="muted">Research, strategy, ads and a campaign plan in about fifteen minutes.</p>
          <NewCampaign tone="light" />
        </section>
      </div>
    </main>
  );
}
