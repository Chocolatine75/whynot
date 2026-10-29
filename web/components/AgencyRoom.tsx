"use client";
import { useEffect, useState } from "react";
import type { PlanAd, RunView, Score, Variant } from "@/lib/runs";
import { STATUS_TAG, ago, eur, fileUrl, joinPhrases, signed, usd } from "@/lib/format";

const CTA_LABEL: Record<string, string> = {
  INSTALL_MOBILE_APP: "Install now", DOWNLOAD: "Download", USE_APP: "Use app", LEARN_MORE: "Learn more",
  SIGN_UP: "Sign up", SUBSCRIBE: "Subscribe",
};

export default function AgencyRoom({ initial }: { initial: RunView }) {
  const [run, setRun] = useState(initial);
  useEffect(() => {
    if (run.status !== "running") return;
    const t = setInterval(async () => {
      const res = await fetch(`/api/run?id=${encodeURIComponent(run.id)}`, { cache: "no-store" });
      if (res.ok) setRun(await res.json());
    }, 2500);
    return () => clearInterval(t);
  }, [run.id, run.status]);

  const [kind, label] = STATUS_TAG[run.status];
  const brand = run.simulation?.brand ?? run.app?.name ?? "Your app";
  const variants = new Map(run.variants.map((v) => [v.variant_id, v]));
  const scores = { ...(run.simulation?.scores ?? {}) };
  for (const g of run.evolution?.groups ?? []) for (const h of g.history) Object.assign(scores, h.scores ?? {});

  return (
    <main className="page" style={{ paddingTop: 32 }}>
      <header className="row" style={{ justifyContent: "space-between", alignItems: "flex-end" }}>
        <div className="stack" style={{ gap: 8 }}>
          <span className={`tag ${kind}`} style={{ alignSelf: "flex-start" }}>{label}</span>
          <h1 style={{ fontSize: 44 }}>{run.app?.name ?? run.config?.app_ref ?? "New campaign"}</h1>
          <p className="muted">
            {run.config?.countries?.join(" · ")} · cap {eur(run.config?.daily_cap_eur ?? 0)}/day · started {ago(run.startedAt)}
          </p>
        </div>
        <div className="metric" style={{ textAlign: "right" }}>
          <span className="label">AI spend</span>
          <span className="value">{usd(run.spentUsd)}</span>
        </div>
      </header>

      <nav className="tabs" style={{ marginTop: 24 }}>
        {[["progress", "Progress"], ["strategy", "Strategy"], ["ads", "Ads"], ["evolution", "Evolution"],
          ["campaign", "Campaign"], ["research", "Research"]].map(([href, text]) => <a key={href} href={`#${href}`}>{text}</a>)}
      </nav>

      <Progress run={run} />
      {run.strategy && <StrategySection run={run} />}
      {run.plan && <AdsSection run={run} brand={brand} variants={variants} scores={scores} />}
      {run.evolution?.groups?.length ? <EvolutionSection run={run} variants={variants} /> : null}
      {run.plan && <CampaignSection run={run} />}
      {run.market && <ResearchSection run={run} />}
    </main>
  );
}

function Progress({ run }: { run: RunView }) {
  const done = run.stages.filter((s) => s.state === "done" || s.state === "cached").length;
  return (
    <section id="progress" className="section" style={{ marginTop: 32 }}>
      <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", alignItems: "start" }}>
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
            <h3>What the agency is doing</h3>
            <span className="small muted num">{done}/{run.stages.length}</span>
          </div>
          <div className="timeline">
            {run.stages.map((s) => (
              <div key={s.stage} className="step">
                <span className={`dot ${s.state}`}>{s.state === "done" || s.state === "cached" ? "✓" : s.state === "error" ? "!" : s.state === "skipped" ? "–" : ""}</span>
                <span style={{ fontWeight: s.state === "running" ? 600 : 400, color: s.state === "pending" || s.state === "skipped" ? "var(--text-2)" : undefined }}>
                  {s.label}{s.state === "skipped" && " (skipped)"}
                  {s.error && <span className="error-text small" style={{ display: "block" }}>{s.error}</span>}
                </span>
                <span className="small muted num">{s.usd > 0 ? usd(s.usd) : ""}</span>
              </div>
            ))}
          </div>
        </div>
        <Summary run={run} />
      </div>
    </section>
  );
}

function Summary({ run }: { run: RunView }) {
  const passed = run.variants.filter((v) => v.guards_passed).length;
  const evolved = run.variants.filter((v) => (v.generation ?? 0) > 0).length;
  const metrics: [string, string, string][] = [
    ["Competitors", `${run.market?.competitors.length ?? "—"}`, `kept of ${run.market?.advertisers_found ?? "—"} found`],
    ["Their ads read", `${run.market?.ads ?? "—"}`, `Ad Library · ${run.market?.research_countries?.join(", ") ?? ""}`],
    ["Reviews read", `${run.app?.reviews.length ?? "—"}`, "App Store"],
    ["Ads made", `${run.variants.length || "—"}`, `${passed} passed every check · ${evolved} evolved`],
  ];
  return (
    <div className="stack">
      <div className="banner info">
        <span>🔒</span>
        <div>
          <strong>Nothing is live.</strong>
          <p className="small muted">The campaign is prepared paused. whynot never spends above your cap and waits for your approval before the first launch.</p>
        </div>
      </div>
      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
        {metrics.map(([l, v, sub]) => (
          <div key={l} className="card metric">
            <span className="label">{l}</span>
            <span className="value">{v}</span>
            <span className="small muted">{sub}</span>
          </div>
        ))}
      </div>
      {run.strategy && <div className="card"><span className="label">Positioning</span><p style={{ marginTop: 6 }}>{run.strategy.positioning}</p></div>}
    </div>
  );
}

function StrategySection({ run }: { run: RunView }) {
  const s = run.strategy!;
  const objections = new Map(s.objections.map((o) => [o.id, o]));
  return (
    <section id="strategy" className="section">
      <h2>Who we target</h2>
      <p className="lede">Customer profiles worth their own ads, from your reviews and the market.</p>
      <div className="grid grid-3">
        {s.personas.map((p) => (
          <div key={p.id} className="card stack" style={{ gap: 10 }}>
            <div className="row" style={{ gap: 8 }}>
              <span className="tag neutral num">{p.age_min}–{p.age_max}</span>
              <span className="tag neutral">{p.gender === "all" ? "Everyone" : p.gender}</span>
              <span className="tag neutral">{p.countries.join(" · ")}</span>
            </div>
            <h3>{p.name}</h3>
            <p className="muted" style={{ fontSize: 15 }}>{p.description}</p>
            <p style={{ fontSize: 15 }}><span className="label">Wants </span>{joinPhrases(p.motivations)}</p>
            <p style={{ fontSize: 15 }}><span className="label">Hesitates </span>{joinPhrases(p.objections.map((o) => objections.get(o)?.text ?? ""))}</p>
          </div>
        ))}
      </div>

      <h2 style={{ marginTop: 48 }}>Why people don&apos;t buy</h2>
      <p className="lede">Each objection comes with the customer&apos;s own words, checked word for word against its source.</p>
      <div className="grid grid-2">
        {s.objections.map((o) => (
          <div key={o.id} className="card stack" style={{ gap: 12 }}>
            <h3>{o.text}</h3>
            {o.evidence.slice(0, 2).map((e) => (
              <blockquote key={e.ref + e.quote} className="quote" style={{ margin: 0 }}>“{e.quote}”<cite>{e.ref.replace(":", " ")}</cite></blockquote>
            ))}
            <p style={{ fontSize: 15 }}><span className="label">How the ads answer </span>{o.answer}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function Post({ run, brand, ad, variant, score }: { run: RunView; brand: string; ad: PlanAd; variant?: Variant; score?: Score }) {
  return (
    <article className="post">
      <div className="post-head">
        <span className="avatar">{brand.slice(0, 1)}</span>
        <div><div className="name">{brand}</div><div className="sponsored">Sponsored</div></div>
      </div>
      <p className="post-text">{ad.body}</p>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={fileUrl(run.id, ad.image_path)} alt={ad.headline_on_image} loading="lazy" />
      <div className="post-cta">
        <span className="title">{ad.title}</span>
        <span className="cta">{CTA_LABEL[ad.cta] ?? ad.cta}</span>
      </div>
      <div className="post-foot">
        {score ? <>
          <span className="tag sim">Simulated</span>
          <span className="small num">{signed(score.lift_over_placebo)} vs competitor</span>
          <span className="small muted num">intent {score.intent.toFixed(1)}/5 · {score.views} views</span>
        </> : <span className="tag neutral">Not simulated</span>}
        {(variant?.generation ?? 0) > 0 && <span className="tag info">Evolved · gen {variant!.generation}</span>}
        {score?.top_why_not?.[0] && <p className="small muted" style={{ width: "100%" }}>Top objection: “{score.top_why_not[0]}”</p>}
      </div>
    </article>
  );
}

function AdsSection({ run, brand, variants, scores }: { run: RunView; brand: string; variants: Map<string, Variant>; scores: Record<string, Score> }) {
  return (
    <section id="ads" className="section">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>The ads</h2>
        <span className="tag sim">Scores are simulated</span>
      </div>
      <p className="lede">Built from your real app screens. Each was tested in a simulated feed next to real competitor ads; the best per audience go in the campaign.</p>
      {run.plan!.ad_sets.map((s) => (
        <div key={s.name} style={{ marginTop: 32 }}>
          <div className="row" style={{ marginBottom: 16 }}>
            <h3>{s.audience.name}</h3>
            <span className="small muted">{s.audience.countries.join(" · ")} · {s.audience.age_min}–{s.audience.age_max} · {eur(s.daily_budget_eur)}/day</span>
          </div>
          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", alignItems: "start" }}>
            {s.ads.map((ad) => <Post key={ad.variant_id} run={run} brand={brand} ad={ad} variant={variants.get(ad.variant_id)} score={scores[ad.variant_id]} />)}
          </div>
        </div>
      ))}
    </section>
  );
}

function EvolutionSection({ run, variants }: { run: RunView; variants: Map<string, Variant> }) {
  const personas = new Map(run.strategy?.personas.map((p) => [p.id, p.name]) ?? []);
  return (
    <section id="evolution" className="section">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>How the ads got better</h2>
        <span className="tag sim">Simulated</span>
      </div>
      <p className="lede">Each round, the agency changed one element of the best ads to answer what viewers objected to, then re-tested them against their parents and against real competitor ads shown under your name.</p>
      {run.evolution!.groups!.map((g) => {
        const chain: Variant[] = [];
        let id: string | null | undefined = g.champion;
        while (id && variants.get(id)) { chain.unshift(variants.get(id)!); id = variants.get(id)!.parent_id; }
        const rounds = g.history.filter((h) => h.scores && h.kept?.length);
        return (
          <div key={g.persona + g.language} className="card" style={{ marginTop: 24 }}>
            <div className="row" style={{ justifyContent: "space-between", marginBottom: 16 }}>
              <h3>{personas.get(g.persona) ?? g.persona}</h3>
              <div className="row" style={{ gap: 8 }}>
                {rounds.map((h) => {
                  const s = h.scores![h.kept![0]];
                  return <span key={h.generation} className="tag neutral num">Round {h.generation}: {signed(s.lift_over_placebo)}</span>;
                })}
              </div>
            </div>
            <div className="lineage">
              {chain.map((v, i) => (
                <div key={v.variant_id} className="row" style={{ flexWrap: "nowrap", alignItems: "stretch", gap: 12 }}>
                  {i > 0 && <span className="arrow">→</span>}
                  <div className="gen">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    {v.image && <img src={fileUrl(run.id, v.image)} alt={v.texts?.hook ?? ""} />}
                    <span className="label">{(v.generation ?? 0) === 0 ? "Original" : `Round ${v.generation}`}</span>
                    {v.mutation
                      ? <p className="small">Changed the <strong>{v.mutation.gene}</strong>: “{v.mutation.text}”<br /><span className="muted">{v.mutation.why}</span></p>
                      : <p className="small muted">{v.texts?.hook}</p>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </section>
  );
}

function CampaignSection({ run }: { run: RunView }) {
  const plan = run.plan!;
  const decisions = new Map(run.launch.map((l) => [l.ad_set, l]));
  const live = run.config?.policy?.level && run.config.policy.level !== "dry_run";
  return (
    <section id="campaign" className="section">
      <h2>The campaign</h2>
      <p className="lede">One ad set per audience, in its language, within your cap. Created paused on Meta until you approve.</p>
      <div className="card raised" style={{ padding: 0, overflow: "hidden" }}>
        <table>
          <thead><tr><th>Ad set</th><th>Who</th><th>Ads</th><th style={{ textAlign: "right" }}>Daily budget</th><th>Launch</th></tr></thead>
          <tbody>
            {plan.ad_sets.map((s) => {
              const d = decisions.get(s.name);
              const tag = d?.outcome === "execute" ? "ok" : d?.outcome === "needs_approval" ? "warn" : d?.outcome === "simulated" ? "sim" : "neutral";
              return (
                <tr key={s.name}>
                  <td><strong>{s.name}</strong></td>
                  <td>{s.audience.name}<div className="small muted">{s.audience.countries.join(" · ")} · {s.audience.age_min}–{s.audience.age_max}</div></td>
                  <td className="num">{s.ads.length}</td>
                  <td className="num" style={{ textAlign: "right" }}>{eur(s.daily_budget_eur)}</td>
                  <td><span className={`tag ${tag}`} title={d?.why}>{d?.outcome?.replace("_", " ") ?? "—"}</span></td>
                </tr>
              );
            })}
            <tr><td colSpan={3}><strong>Total</strong></td><td className="num" style={{ textAlign: "right" }}><strong>{eur(plan.daily_total_eur)}</strong> <span className="muted small">of {eur(plan.daily_cap_eur)}</span></td><td /></tr>
          </tbody>
        </table>
      </div>
      {plan.errors.length > 0 && <div className="banner bad" style={{ marginTop: 16 }}><strong>Plan problems:</strong> {plan.errors.join("; ")}</div>}
      {plan.notes.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <span className="label">Notes</span>
          <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>{plan.notes.map((n) => <li key={n} className="small">{n}</li>)}</ul>
        </div>
      )}
      <div className="row" style={{ marginTop: 24, justifyContent: "space-between" }}>
        <p className="small muted" style={{ maxWidth: 560 }}>
          {live ? "Approving publishes the ad sets on your Meta account within your cap."
                : "Dry-run mode: approving simulates the launch. Connect your Meta ad account and set a live cap to go live."}
        </p>
        <button className="btn large" disabled title="Publishing to Meta is not connected yet">Approve launch</button>
      </div>
    </section>
  );
}

function ResearchSection({ run }: { run: RunView }) {
  const m = run.market!;
  const names = new Map((m.advertisers ?? []).map((a) => [a.page_id, a]));
  return (
    <section id="research" className="section">
      <h2>The market</h2>
      <p className="lede">Competitors found in the Meta Ad Library ({m.research_countries.join(", ")}), filtered to those selling the same thing. Searched for: {m.terms.join(", ")}.</p>
      <div className="grid grid-3">
        {m.competitors.map((c) => (
          <div key={c.page_id} className="card tight stack" style={{ gap: 4 }}>
            <strong>{names.get(c.page_id)?.page_name ?? c.page_id}</strong>
            <span className="small muted">{c.why}</span>
            <span className="small num">{names.get(c.page_id)?.ads ?? 0} ads seen</span>
          </div>
        ))}
      </div>
      <p className="small muted" style={{ marginTop: 16 }}>{m.rejected.length} unrelated advertisers ignored.</p>
    </section>
  );
}
