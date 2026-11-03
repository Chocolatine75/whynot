"use client";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { MarketAd, PlanAd, Progress, RunView, Score, StageState, Variant } from "@/lib/runs";
import AppIcon from "@/components/AppIcon";
import AgencyPanel from "@/components/AgencyPanel";
import PublishPanel from "@/components/PublishPanel";
import { Alert, ArrowRight } from "@/components/Icons";
import { STATUS_TAG, ago, eur, fileUrl, joinPhrases, usd } from "@/lib/format";

const CTA_LABEL: Record<string, string> = {
  INSTALL_MOBILE_APP: "Install now", DOWNLOAD: "Download", USE_APP: "Use app", LEARN_MORE: "Learn more",
  SIGN_UP: "Sign up", SUBSCRIBE: "Subscribe",
};
/** Who does each stage, and with which Meta model: shown in the live log and on the timeline. */
const AGENT: Record<string, string> = {
  app: "Scout", market: "Scout · Ad Library", strategy: "Strategist · Muse Wonder", creative: "Creative director · Muse Spark",
  produce: "Producer · SAM 3.1 + code", simulate: "Viewer agents · Muse Spark Open", evolve: "Evolver · Muse Spark",
  plan: "Planner", report: "Account manager",
};
const initials = (s: string) => s.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
const times = (n: number) => `${n.toFixed(1)}×`;
const short = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("en", { month: "short", day: "numeric", timeZone: "UTC" }) : "");

/** "review:1450…" → "App Store review"; "ad:<id>" → "Falou ad, 118 days"; "store" → "Store page". */
function source(ref: string, ads: Map<string, MarketAd>): string {
  const [kind, id] = ref.split(":");
  if (kind === "review") return "App Store review";
  if (kind === "store") return "Store page";
  if (kind === "ad") {
    const a = ads.get(id);
    return a ? `${a.pageName} ad${a.days !== null ? `, running ${a.days} days` : ""}` : "Competitor ad";
  }
  return ref;
}

type Section = { id: string; label: string; state?: StageState };

export default function AgencyRoom({ initial }: { initial: RunView }) {
  const [run, setRun] = useState(initial);
  const seq = useRef(0);
  const refresh = useCallback(async () => {
    const n = ++seq.current;  // a slow answer never overwrites a newer one
    try {
      const res = await fetch(`/api/run?id=${encodeURIComponent(initial.id)}`, { cache: "no-store" });
      if (res.ok && n === seq.current) setRun(await res.json());
    } catch { /* keep the last good state */ }
  }, [initial.id]);
  useEffect(() => {
    if (run.status !== "running") return;
    const t = setInterval(() => { if (!document.hidden) void refresh(); }, 2500);
    return () => clearInterval(t);
  }, [refresh, run.status]);

  const sim = run.simulation;
  const untested = sim !== null && !sim.simulated;
  const stage = (s: string): StageState | undefined => {
    const st = run.stages.find((x) => x.stage === s)?.state;
    return untested && (s === "simulate" || s === "evolve") && (st === "done" || st === "cached") ? "skipped" : st;
  };
  const scores = useMemo(() => {
    const out: Record<string, Score> = { ...(run.simulation?.scores ?? {}) };
    for (const g of run.evolution?.groups ?? []) for (const h of g.history) Object.assign(out, h.scores ?? {});
    return out;
  }, [run.simulation, run.evolution]);
  const variants = useMemo(() => new Map(run.variants.map((v) => [v.variant_id, v])), [run.variants]);
  const personas = useMemo(() => new Map(run.strategy?.personas.map((p) => [p.id, p.name]) ?? []), [run.strategy]);
  const ads = useMemo(() => new Map(run.marketAds.map((a) => [a.id, a])), [run.marketAds]);
  const brand = run.simulation?.brand ?? run.app?.name ?? "Your app";
  const name = run.app?.name ?? run.config?.app_ref ?? "New campaign";
  const canApprove = run.agency ? run.agency.waiting : Boolean(run.plan) && run.status === "done" && !run.published;

  const sections: Section[] = [
    { id: "overview", label: "Overview" },
    { id: "best", label: "Best ads", state: stage("produce") },
    { id: "test", label: "Simulated test", state: stage("simulate") },
    { id: "evolution", label: "Evolution", state: stage("evolve") },
    ...(run.videos.length ? [{ id: "videos", label: "Video ads" }] : []),
    { id: "ads", label: "Every ad", state: stage("produce") },
    { id: "market", label: "Market", state: stage("market") },
    { id: "strategy", label: "Strategy", state: stage("strategy") },
    { id: "launch", label: "Launch", state: stage("plan") },
  ];
  const active = useScrollSpy(sections.map((s) => s.id));
  const ctx = { run, variants, scores, personas, ads, brand, untested };

  return (
    <div className="room">
      <aside className="side" aria-label="Campaign sections">
        <Link href="/runs" className="back small">← Campaigns</Link>
        <nav className="side-nav">
          {sections.map((s) => (
            <a key={s.id} href={`#${s.id}`} className={active === s.id ? "active" : undefined}>
              {s.label}
              {s.state && ["running", "error", "skipped"].includes(s.state) && <span className={`state ${s.state}`} title={s.state} />}
            </a>
          ))}
        </nav>
        <div className="side-foot">
          {canApprove && <a href="#launch" className="btn magnetic">Review &amp; approve</a>}
          <div className="meter"><span>AI cost (USD)</span><strong>{usd(run.spentUsd)}</strong></div>
          <div className="meter"><span>Ad budget cap</span><strong>{eur(run.config?.daily_cap_eur ?? 0)}/day</strong></div>
        </div>
      </aside>

      <main className="main" id="content">
        <Overview {...ctx} name={name} canApprove={canApprove} stage={stage} />
        <Best {...ctx} />
        <Test {...ctx} />
        <Evolution {...ctx} />
        {run.videos.length > 0 && <Videos {...ctx} />}
        <AllAds {...ctx} />
        <Market {...ctx} />
        <StrategySection {...ctx} />
        <Launch run={run} onRefresh={refresh} />
      </main>
      {canApprove && <a href="#launch" className="btn lg approve-bar">Review &amp; approve</a>}
    </div>
  );
}

interface Ctx {
  run: RunView; variants: Map<string, Variant>; scores: Record<string, Score>; personas: Map<string, string>;
  ads: Map<string, MarketAd>; brand: string; untested: boolean;
}

/** The section in view, for the side navigation. */
function useScrollSpy(ids: string[]) {
  const [active, setActive] = useState(ids[0]);
  const key = ids.join(",");
  useEffect(() => {
    const list = key.split(",");
    const els = list.map((id) => document.getElementById(id)).filter((e): e is HTMLElement => Boolean(e));
    const top = window.matchMedia("(max-width: 960px)").matches ? 124 : 70; // under the sticky bars
    const obs = new IntersectionObserver((entries) => {
      const seen = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (seen[0]) setActive(seen[0].target.id);
    }, { rootMargin: `-${top}px 0px -65% 0px` });
    els.forEach((e) => obs.observe(e));
    // a short last section never reaches the line: at the bottom of the page it is the one in view
    const onScroll = () => { if (innerHeight + scrollY >= document.documentElement.scrollHeight - 4) setActive(list[list.length - 1]); };
    addEventListener("scroll", onScroll, { passive: true });
    return () => { obs.disconnect(); removeEventListener("scroll", onScroll); };
  }, [key]);
  useEffect(() => {
    document.querySelector(`.side-nav a[href="#${active}"]`)?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [active]);
  return active;
}

function Head({ eyebrow, title, text, aside }: { eyebrow: string; title: string; text?: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <div className="sec-head reveal">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h2>{title}</h2>
        {text && <p>{text}</p>}
      </div>
      {aside}
    </div>
  );
}

function Waiting({ what }: { what: string }) {
  return <div className="card empty small">{what}</div>;
}

function Sub({ children }: { children: React.ReactNode }) {
  return <h3 className="sub-title">{children}</h3>;
}

function More({ total, shown, onClick, noun }: { total: number; shown: number; onClick: () => void; noun: string }) {
  if (total <= shown) return null;
  return <button className="btn secondary sm more" onClick={onClick}>Show {total - shown} more {noun}</button>;
}

/** The best plan ad of each ad set (highest simulated score), with its set. */
function bestAds(run: RunView, scores: Record<string, Score>) {
  return (run.plan?.ad_sets ?? []).flatMap((s) => {
    const ad = [...s.ads].sort((a, b) => (scores[b.variant_id]?.lift_over_placebo ?? -99) - (scores[a.variant_id]?.lift_over_placebo ?? -99))[0];
    return ad ? [{ set: s, ad }] : [];
  });
}

// ---------- overview ----------

function Overview({ run, name, canApprove, stage, untested }: Ctx & { name: string; canApprove: boolean; stage: (s: string) => StageState | undefined }) {
  const [kind, label] = STATUS_TAG[run.status];
  const kept = run.plan?.ad_sets.reduce((n, s) => n + s.ads.length, 0) ?? 0;
  const passed = run.variants.filter((v) => v.guards_passed).length;
  const pub = run.published;
  const first = run.log[0]?.ts ?? run.startedAt;
  const last = run.log.at(-1)?.ts;
  const minutes = first && last ? Math.max(1, Math.round((Date.parse(last) - Date.parse(first)) / 60_000)) : null;
  const running = run.status === "running";
  const stats: [string, string, string][] = [
    ["Competitor ads read", `${run.market?.ads ?? 0}`, run.market?.ads ? `${run.market.competitors.length} competitors, Meta Ad Library` : "none listed for this category"],
    ["Customer profiles", `${run.strategy?.personas.length ?? "…"}`, "each with its own ads"],
    ["Ads made → kept", run.variants.length ? `${run.variants.length} → ${kept}` : "…", run.variants.length ? `${passed} of ${run.variants.length} use the real app screen` : "statics"],
    ...(run.videos.length ? [["Video ads", `${run.videos.length}`, "voiced, captioned, checked by ear"] as [string, string, string]] : []),
    ["AI cost (USD)", usd(run.spentUsd), minutes ? `every call metered · ${minutes} min` : "every call metered"],
  ];
  return (
    <section id="overview" className="sec">
      <div className="hero">
        <div className="hero-id">
          <AppIcon run={run.id} icon={run.icon} name={name} size="lg" />
          <div style={{ minWidth: 0 }}>
            <h1>{name}</h1>
            <div className="hero-meta">
              {run.app?.rating ? <span className="num">★ {run.app.rating.toFixed(1)} · {run.app.rating_count.toLocaleString("en")} ratings</span> : null}
              {run.config?.countries?.length ? <span>Ads for {run.config.countries.join(", ")}</span> : null}
              {run.startedAt && <span suppressHydrationWarning>started {ago(run.startedAt)}</span>}
            </div>
          </div>
        </div>
        {canApprove && <a href="#launch" className="btn lg hide-sm magnetic">Review &amp; approve</a>}
      </div>

      <div className="stack" style={{ marginTop: 24, gap: 20 }}>
        <div className="row" style={{ gap: 8 }}>
          <span className={`tag dot ${untested && run.status === "done" ? "warn" : kind}`}>
            {run.status === "done" ? (untested ? "Ready, not tested in a feed" : pub ? "Published" : "Ready for your approval") : label}
          </span>
          <span className="small muted">
            {pub && Object.keys(pub.objects).length > 0
              ? `${pub.mode === "live" ? "On your Meta account" : "In the sandbox"}, ${pub.status === "active" ? "delivering" : "paused"} · approved by ${pub.approved_by ?? "—"}`
              : `Nothing is live · prepared paused within your ${eur(run.config?.daily_cap_eur ?? 0)}/day cap`}
          </span>
        </div>

        {running && <LiveLog run={run} />}

        <div className="stats reveal">
          {stats.map(([l, v, d]) => (
            <div key={l} className="stat"><div className="label">{l}</div><div className="v">{v}</div><div className="d">{d}</div></div>
          ))}
        </div>

        <details className="timeline" open={running || run.status === "failed"}>
          <summary>
            <span>How the agency worked</span>
            <span className="faint small num">{run.stages.filter((s) => s.state === "done" || s.state === "cached").length} of {run.stages.length} steps{minutes ? ` · ${minutes} min` : ""} · {usd(run.spentUsd)}</span>
          </summary>
          <div className="pipeline">
            {run.stages.map((s) => {
              const st = stage(s.stage) ?? s.state;
              return (
                <div key={s.stage} className={`pipe ${st}`} title={s.error ?? s.label}>
                  <div className="bar" />
                  <span className="t">{s.label}</span>
                  <span className="a">{AGENT[s.stage]}</span>
                  <span className="c">{st === "skipped" ? "skipped" : st === "running" ? "working…" : s.usd > 0 ? usd(s.usd) : st === "done" || st === "cached" ? "$0 · code" : ""}</span>
                </div>
              );
            })}
          </div>
        </details>
        {run.stages.some((s) => s.error) && (
          <div className="notice bad"><Alert /><span>{run.stages.find((s) => s.error)?.error}</span></div>
        )}

        {run.strategy?.positioning && (
          <figure className="pull">
            <blockquote>{run.strategy.positioning}</blockquote>
            <figcaption>Positioning · written by Muse Wonder from {run.app?.reviews.length ?? 0} reviews, the store page{run.market?.ads ? ` and ${run.market.ads} competitor ads` : ""}</figcaption>
          </figure>
        )}
      </div>
    </section>
  );
}

/** While the agency works: what each agent is doing, newest first. */
function LiveLog({ run }: { run: RunView }) {
  const lines = [...run.log].reverse().slice(0, 8);
  return (
    <div className="card live" aria-live="polite">
      <div className="spread" style={{ marginBottom: 10 }}>
        <h2 className="h4"><span className="pulse-dot" aria-hidden /> Agents at work</h2>
        <span className="small faint mono">{usd(run.spentUsd)} so far</span>
      </div>
      <ol className="log">
        {lines.map((e, i) => (
          <li key={`${e.ts}${e.stage}${e.status}${i}`}>
            <span className="mono faint">{e.ts.slice(11, 19)}</span>
            <span><strong>{AGENT[e.stage] ?? e.stage}</strong> · {e.status === "start" ? "started" : e.status === "ok" ? "done" : e.status}{" "}
              <span className="muted">{run.stages.find((s) => s.stage === e.stage)?.label.toLowerCase()}</span></span>
            <span className="mono faint">{e.usd ? usd(e.usd) : ""}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

// ---------- ads ----------

function Post({ run, brand, ad, variant, score, best }: { run: RunView; brand: string; ad: PlanAd; variant?: Variant; score?: Score; best?: boolean }) {
  return (
    <article className="post spot tilt" data-tilt="5">
      <div className="post-head">
        <AppIcon run={run.id} icon={run.icon} name={brand} size="sm" />
        <div><div className="n">{brand}</div><div className="s">Sponsored</div></div>
        {best && <span className="tag info" style={{ marginLeft: "auto" }}>Best in test</span>}
      </div>
      <p className="post-text"><span>{ad.body}</span></p>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={fileUrl(run.id, ad.image_path)} alt={ad.headline_on_image} loading="lazy" width={1080} height={1080} />
      <div className="post-cta">
        <span className="t">{ad.title}</span>
        <span className="b">{CTA_LABEL[ad.cta] ?? ad.cta}</span>
      </div>
      <div className="post-foot">
        {score ? (
          <div className="score">
            <span className="big">{times(score.lift)}</span>
            <span className="small muted">picked vs chance · would install {score.intent.toFixed(1)}/5</span>
          </div>
        ) : <span className="small faint">Not tested in a feed</span>}
        <div className="row" style={{ gap: 6 }}>
          {(variant?.generation ?? 0) > 0 && <span className="tag neutral">Improved {variant!.generation === 1 ? "once" : `${variant!.generation} times`}</span>}
          {variant?.guards_passed && <span className="tag neutral" title="Its app pixels are identical to the store screenshot">✓ Real app screen</span>}
        </div>
        {score?.top_why_not?.[0] && <p className="obj">“{score.top_why_not[0]}”</p>}
      </div>
    </article>
  );
}

function Best({ run, scores, variants, personas, brand }: Ctx) {
  const best = bestAds(run, scores);
  return (
    <section id="best" className="sec">
      <Head eyebrow="Ready to launch" title="Your best ads"
            text="One winner per customer."
            aside={Object.keys(scores).length ? <span className="tag sim">Simulated</span> : undefined} />
      {best.length === 0 ? <Waiting what="The creative director is writing concepts…" /> : (
        <div className="posts reveal">
          {best.map(({ set, ad }) => (
            <div key={ad.variant_id} className="stack" style={{ gap: 8 }}>
              <span className="small"><strong>{personas.get(set.audience.persona.split(".")[0]) ?? set.audience.name}</strong> <span className="faint">· {eur(set.daily_budget_eur)}/day</span></span>
              <Post run={run} brand={brand} ad={ad} variant={variants.get(ad.variant_id)} score={scores[ad.variant_id]} best={Boolean(scores[ad.variant_id])} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function AllAds({ run, brand, variants, scores }: Ctx) {
  const sets = run.plan?.ad_sets ?? [];
  const [pick, setPick] = useState(0);
  const set = sets[Math.min(pick, sets.length - 1)];
  return (
    <section id="ads" className="sec">
      <Head eyebrow="Creative · SAM 3.1 + code" title="Every ad in the campaign"
            text={run.variants.length > 0 ? `${run.variants.length} made, ${sets.reduce((n, s) => n + s.ads.length, 0)} kept. Real app screens, never generated.` : undefined} />
      {!set ? <Waiting what="The ads come after the strategy." /> : (
        <div className="stack" style={{ gap: 18 }}>
          {sets.length > 1 && (
            <div className="seg" role="group" aria-label="Audience">
              {sets.map((s, i) => <button key={s.name} aria-pressed={i === pick} onClick={() => setPick(i)}>{s.audience.name}</button>)}
            </div>
          )}
          <p className="small muted">{set.audience.countries.join(", ")} · ages {set.audience.age_min}–{set.audience.age_max} · {eur(set.daily_budget_eur)}/day</p>
          <div className="posts reveal">
            {set.ads.map((ad) => <Post key={ad.variant_id} run={run} brand={brand} ad={ad} variant={variants.get(ad.variant_id)} score={scores[ad.variant_id]} />)}
          </div>
        </div>
      )}
    </section>
  );
}

// ---------- videos ----------

function Videos({ run, personas }: Ctx) {
  const [all, setAll] = useState(false);
  const shown = all ? run.videos : run.videos.slice(0, 4);
  return (
    <section id="videos" className="sec">
      <Head eyebrow="Video ads · Muse Image, SAM 3.1, Voice Transcribe" title="Short videos on what's trending"
            text="Checked by ear before they ship." />
      <div className="reels reveal">
        {shown.map((v) => (
          <article key={v.path} className="reel">
            <div className="phone tilt" data-tilt="10">
              <video src={fileUrl(run.id, v.path)} poster={v.poster ? fileUrl(run.id, v.poster) : undefined} controls playsInline preload="none" />
            </div>
            <div className="row" style={{ gap: 6 }}>
              {v.tone && <span className="tag neutral">{v.tone}</span>}
              <span className="tag neutral num">{Math.round(v.seconds)} s</span>
              {v.wordErrorRate !== null && (
                <span className={`tag ${v.flags.length ? "warn" : "ok"}`} title={v.flags.join("; ") || "The transcription of the final mix matches the captions"}>
                  {v.flags.length ? `${v.flags.length} QA flag${v.flags.length > 1 ? "s" : ""}` : "✓ Checked by ear"}
                </span>
              )}
            </div>
            <p className="hook">{v.hook}</p>
            <p className="xsmall faint">{personas.get(v.persona) ?? v.persona}</p>
          </article>
        ))}
      </div>
      <More total={run.videos.length} shown={shown.length} onClick={() => setAll(true)} noun="videos" />
    </section>
  );
}

// ---------- simulated test ----------

/** A phone showing the simulated feed: real competitor ads, ours in the middle, a viewer agent's reaction on it. */
function FeedPhone({ run, brand, ad, score, competitors }: { run: RunView; brand: string; ad: PlanAd; score?: Score; competitors: MarketAd[] }) {
  const Comp = ({ a }: { a: MarketAd }) => (
    <div className="fp-post">
      <div className="fp-head"><span className="avatar sm">{initials(a.pageName)}</span><div><b>{a.pageName}</b><i>Sponsored · real ad, {a.days ?? "?"} days</i></div></div>
      <p>{a.body}</p>
      {a.title && <div className="fp-title">{a.title}</div>}
    </div>
  );
  return (
    <div className="feed-phone tilt" data-tilt="6" aria-label="Simulated feed">
      <div className="fp-bar"><span>Feed</span><span className="tag sim">Simulated</span></div>
      <div className="fp-scroll">
        {competitors[0] && <Comp a={competitors[0]} />}
        <div className="fp-post ours">
          <div className="fp-head"><AppIcon run={run.id} icon={run.icon} name={brand} size="sm" /><div><b>{brand}</b><i>Sponsored · our ad</i></div></div>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={fileUrl(run.id, ad.image_path)} alt={ad.headline_on_image} />
          {score && (
            <div className="reaction">
              <span className="avatar sm viewer">VA</span>
              <div>
                <b>Viewer agent</b>
                <p>{score.top_why_not[0] ? `Why not: “${score.top_why_not[0]}”` : "Picked this one."}</p>
                <i>picked {times(score.lift)} chance · would install {score.intent.toFixed(1)}/5</i>
              </div>
            </div>
          )}
        </div>
        {competitors[1] && <Comp a={competitors[1]} />}
      </div>
    </div>
  );
}

function Test({ run, variants, scores, personas, brand, untested }: Ctx) {
  const sim = run.simulation;
  const groups = sim?.groups ?? [];
  const [pick, setPick] = useState(0);
  const g = groups[Math.min(pick, groups.length - 1)];
  const rows = g ? run.variants.filter((v) => v.persona === g.persona && v.language === g.language && scores[v.variant_id] && (v.generation ?? 0) === 0)
    .map((v) => ({ v, s: scores[v.variant_id] })).sort((a, b) => b.s.lift - a.s.lift) : [];
  const max = Math.max(1, ...rows.map((r) => r.s.lift), g?.placebo_lift ?? 0);
  const whyNot = [...new Set(rows.flatMap((r) => r.s.top_why_not.slice(0, 1)))].slice(0, 4);
  const best = bestAds(run, scores).find((b) => b.set.audience.persona.split(".")[0] === g?.persona) ?? bestAds(run, scores)[0];
  const competitors = run.marketAds.filter((a) => a.body).slice(0, 2);
  const multiLang = new Set(groups.map((x) => x.language)).size > 1;
  return (
    <section id="test" className="sec">
      <Head eyebrow="Simulated feed · viewer agents on Muse Spark Open" title="Tested before a cent is spent"
            text="Between your competitors' real ads, judged by agents playing your customers."
            aside={<span className="tag sim">Simulated viewers, not real people</span>} />
      {!sim ? <Waiting what="Waiting for the ads to be made…" /> : untested ? (
        <div className="notice"><Alert /><span><strong>Not tested in a feed for this app.</strong> <span className="muted">No competitor ads to test against.</span></span></div>
      ) : (
        <div className="stack" style={{ gap: 20 }}>
          {groups.length > 1 && (
            <div className="seg" role="group" aria-label="Audience">
              {groups.map((x, i) => <button key={x.persona + x.language} aria-pressed={i === pick} onClick={() => setPick(i)}>{personas.get(x.persona) ?? x.persona}{multiLang ? ` · ${x.language}` : ""}</button>)}
            </div>
          )}
          <div className="test-grid reveal">
            {best && <FeedPhone run={run} brand={brand} ad={best.ad} score={scores[best.ad.variant_id]} competitors={competitors} />}
            <div className="stack" style={{ gap: 16, minWidth: 0 }}>
              <div className="card flush scroll-x">
                <table className="board">
                  <thead><tr><th colSpan={2}>Ad</th><th>Picked, vs chance</th><th className="r">Would install</th><th className="r">Viewers</th></tr></thead>
                  <tbody>
                    {rows.map(({ v, s }) => (
                      <tr key={v.variant_id}>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <td style={{ width: 56 }}>{v.image && <img className="thumb" src={fileUrl(run.id, v.image)} alt="" loading="lazy" />}</td>
                        <td style={{ minWidth: 180 }}><div style={{ fontWeight: 500 }}>{v.texts?.hook ?? v.template_id}</div><div className="xsmall faint mono">{v.variant_id.slice(-8)}</div></td>
                        <td><Bar value={s.lift} max={max} /></td>
                        <td className="r num mono small">{s.intent.toFixed(1)}/5</td>
                        <td className="r num mono small">{s.views}</td>
                      </tr>
                    ))}
                    {g?.placebo_lift !== undefined && (
                      <tr className="placebo">
                        <td><span className="thumb blank" /></td>
                        <td><div>Dummy ad (placebo)</div><div className="xsmall faint">no message, same feeds</div></td>
                        <td><Bar value={g.placebo_lift} max={max} muted /></td>
                        <td className="r num mono small">{g.placebo_intent !== undefined ? `${g.placebo_intent.toFixed(1)}/5` : "—"}</td>
                        <td className="r num mono small">{g.placebo_views ?? "—"}</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              <p className="xsmall faint footnote">1.0× = a random pick. Small gaps are noise. <Link href="/validation">How reliable is this?</Link></p>
            </div>
          </div>
          {whyNot.length > 0 && (
            <div>
              <Sub>Why not, in the viewers&apos; words</Sub>
              <div className="whynot">{whyNot.map((w) => <blockquote key={w} className="quote card">“{w}”</blockquote>)}</div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function Bar({ value, max, muted }: { value: number; max: number; muted?: boolean }) {
  return (
    <div className="lift">
      <div className="track"><div className={`fill${muted ? " muted" : ""}`} style={{ width: `${Math.max(2, (value / max) * 100)}%` }} /></div>
      <span className="num mono small" style={{ width: 40, textAlign: "right" }}>{times(value)}</span>
    </div>
  );
}

// ---------- evolution ----------

function ProgressChart({ points }: { points: Progress[] }) {
  const W = 520, H = 180, P = 28;
  const lo = Math.min(...points.flatMap((p) => [p.ci?.[0] ?? p.strength, p.placebo ?? p.strength]), 0);
  const hi = Math.max(...points.flatMap((p) => [p.ci?.[1] ?? p.strength, p.placebo ?? p.strength]), 1);
  const x = (i: number) => P + (i * (W - 2 * P)) / Math.max(1, points.length - 1);
  const y = (v: number) => H - P - ((v - lo) / (hi - lo || 1)) * (H - 2 * P);
  const placebo = points.filter((p) => typeof p.placebo === "number");
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Head-to-head strength of the best ad per generation, with 95 % intervals">
      <line className="axis" x1={P} x2={W - P} y1={H - P} y2={H - P} />
      {placebo.length > 1 && <polyline className="placebo" points={placebo.map((p) => `${x(points.indexOf(p))},${y(p.placebo!)}`).join(" ")} />}
      {points.map((p, i) => p.ci && <line key={`ci${i}`} className="ci" x1={x(i)} x2={x(i)} y1={y(p.ci[0])} y2={y(p.ci[1])} />)}
      <polyline className="line" points={points.map((p, i) => `${x(i)},${y(p.strength)}`).join(" ")} />
      {points.map((p, i) => <circle key={i} className="pt" cx={x(i)} cy={y(p.strength)} r={4.5}><title>{`gen ${p.generation}: ${p.strength.toFixed(2)}`}</title></circle>)}
      {points.map((p, i) => <text key={`t${i}`} x={x(i)} y={H - 8} textAnchor="middle">gen {p.generation}</text>)}
    </svg>
  );
}

function verdictText(r: { verdict: string; difference: number; noise_floor: number | null; generation: number }): [string, string] {
  const gap = `${r.difference >= 0 ? "+" : "−"}${Math.abs(r.difference).toFixed(1)}`;
  const noise = r.noise_floor !== null ? ` (noise ±${r.noise_floor.toFixed(1)})` : "";
  if (r.verdict === "improved") return ["ok", `Generation ${r.generation} beats the original: ${gap} head-to-head${noise}`];
  if (r.verdict === "worse") return ["bad", `Generation ${r.generation} is worse than the original: ${gap}${noise}`];
  if (r.verdict === "within noise") return ["neutral", `Not clearly better than the original: ${gap} is within the noise${noise}`];
  return ["warn", `Gap ${gap}: noise not measured, not called a win`];
}

function Evolution({ run, variants, scores, personas, untested }: Ctx) {
  const groups = run.evolution?.groups ?? [];
  return (
    <section id="evolution" className="sec">
      <Head eyebrow="Evolution · Muse Spark" title="How the ads got better"
            text="One change per round, kept only if it wins head to head."
            aside={groups.length ? <span className="tag sim">Simulated</span> : undefined} />
      {groups.length === 0 ? <Waiting what={untested ? "No evolution without a feed to test in." : run.evolution?.skipped ?? "Evolution runs after the simulated test."} /> : (
        <div className="stack" style={{ gap: 16 }}>
          {groups.map((g) => {
            const chain: Variant[] = [];
            let id: string | null | undefined = g.champion;
            while (id && variants.get(id) && chain.length < 8) { chain.unshift(variants.get(id)!); id = variants.get(id)!.parent_id; }
            const [origin, champion] = [chain[0], chain.at(-1)];
            const changes = chain.slice(1).filter((v) => v.mutation);
            const verdict = g.result ? verdictText(g.result) : null;
            return (
              <div key={g.persona + g.language} className="card pad-lg stack spot" style={{ gap: 20 }}>
                <div className="spread">
                  <h3>{personas.get(g.persona) ?? g.persona}</h3>
                  {verdict && <span className={`tag ${verdict[0]}`}>{verdict[1]}</span>}
                </div>
                {origin && champion && origin !== champion ? (
                  <div className="before-after">
                    <Gen run={run} v={origin} label="Original" score={scores[origin.variant_id]} />
                    <ol className="changes">
                      {changes.map((v) => (
                        <li key={v.variant_id}>
                          <span className="eyebrow">Round {v.generation} · changed the {v.mutation!.gene}</span>
                          <p className="small">“{v.mutation!.text}”</p>
                          <p className="xsmall faint">{v.mutation!.why}</p>
                        </li>
                      ))}
                      <ArrowRight className="arrow" />
                    </ol>
                    <Gen run={run} v={champion} label={`Winner · generation ${champion.generation}`} score={scores[champion.variant_id]} />
                  </div>
                ) : <p className="small muted">The original stayed the best: no change beat it.</p>}
                {g.progress && g.progress.length > 1 && (
                  <details>
                    <summary className="small">Strength per generation, with 95 % intervals</summary>
                    <ProgressChart points={g.progress} />
                  </details>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function Gen({ run, v, label, score }: { run: RunView; v: Variant; label: string; score?: Score }) {
  return (
    <figure className="gen">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {v.image && <img src={fileUrl(run.id, v.image)} alt={v.texts?.hook ?? ""} loading="lazy" />}
      <figcaption>
        <span className="eyebrow">{label}</span>
        {score && <span className="small mono">picked {times(score.lift)} · install {score.intent.toFixed(1)}/5</span>}
      </figcaption>
    </figure>
  );
}

// ---------- market ----------

function Market({ run }: Ctx) {
  const [who, setWho] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  const m = run.market;
  const ads = run.marketAds.filter((a) => !who || a.pageName === who);
  const shown = all ? ads : ads.slice(0, 6);
  const pages = [...new Set(run.marketAds.map((a) => a.pageName))].slice(0, 8);
  const researched = m?.research_countries.join(", ") ?? "";
  return (
    <section id="market" className="sec">
      <Head eyebrow="Research · Meta Ad Library" title="What your competitors run"
            text={m?.ads ? `${m.ads} ads from ${m.competitors.length} advertisers (${researched}), longest-running first.` : undefined} />
      {!m ? <Waiting what="The scout is reading the Ad Library…" /> : m.ads === 0 ? (
        <div className="notice"><Alert /><span><strong>No competitor ads found.</strong> <span className="muted">This category has none in the EU/UK Ad Library. The strategy uses your reviews instead.</span></span></div>
      ) : (
        <div className="stack" style={{ gap: 18 }}>
          {pages.length > 1 && (
            <div className="seg" role="group" aria-label="Filter by advertiser">
              <button aria-pressed={who === null} onClick={() => { setWho(null); setAll(false); }}>All</button>
              {pages.map((p) => <button key={p} aria-pressed={who === p} onClick={() => { setWho(p); setAll(false); }}>{p}</button>)}
            </div>
          )}
          <div className="ads-lib">
            {shown.map((a) => (
              <article key={a.id} className="lib-ad spot">
                <div className="who">
                  <span className="avatar">{initials(a.pageName)}</span>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div className="small" style={{ fontWeight: 600 }}>{a.pageName}</div>
                    <div className="xsmall faint">Sponsored · {a.platforms.length} placements{a.startDate ? ` · since ${short(a.startDate)}` : ""}</div>
                  </div>
                  {a.days !== null && <span className={`tag ${a.days >= 60 ? "ok" : "neutral"} num`}>{a.days} days</span>}
                </div>
                {a.body && <p className="body">{a.body}</p>}
                {a.title && <p className="small" style={{ fontWeight: 600 }}>{a.title}</p>}
              </article>
            ))}
          </div>
          <More total={ads.length} shown={shown.length} onClick={() => setAll(true)} noun="ads" />
        </div>
      )}
    </section>
  );
}

// ---------- strategy ----------

function StrategySection({ run, ads }: Ctx) {
  const s = run.strategy;
  const [allObj, setAllObj] = useState(false);
  const [allAngles, setAllAngles] = useState(false);
  const objections = new Map(s?.objections.map((o) => [o.id, o]) ?? []);
  const personaName = new Map(s?.personas.map((p) => [p.id, p.name]) ?? []);
  const market = (run.market?.ads ?? 0) > 0;
  return (
    <section id="strategy" className="sec">
      <Head eyebrow="Strategy · Muse Wonder" title="Who to talk to, and why they don't install yet"
            text="Every objection quoted from a real source." />
      {!s ? <Waiting what="The strategist is reading the market and your reviews…" /> : (
        <div className="stack" style={{ gap: 8 }}>
          <div className="personas">
            {s.personas.map((p) => (
              <div key={p.id} className="card persona spot">
                <div className="who">
                  <span className="avatar lg">{initials(p.name)}</span>
                  <div>
                    <h3>{p.name}</h3>
                    <div className="xsmall faint num">{p.age_min}–{p.age_max} · {p.gender === "all" ? "everyone" : p.gender} · {p.countries.join(", ")}</div>
                  </div>
                </div>
                <div className="lists">
                  <div><span className="label">Wants</span><ul>{p.motivations.slice(0, 3).map((m) => <li key={m}>{joinPhrases([m])}</li>)}</ul></div>
                  <div><span className="label">Hesitates</span><ul>{p.objections.slice(0, 2).map((o) => <li key={o}>{joinPhrases([objections.get(o)?.text ?? ""])}</li>)}</ul></div>
                </div>
              </div>
            ))}
          </div>

          <Sub>Why people say no</Sub>
          <div className="objections">
            {(allObj ? s.objections : s.objections.slice(0, 4)).map((o) => (
              <div key={o.id} className="card stack spot" style={{ gap: 12 }}>
                <h4>{o.text}</h4>
                {o.evidence.slice(0, 1).map((e, i) => (
                  <blockquote key={`${i}-${e.ref}`} className="quote">“{e.quote}”<cite>{source(e.ref, ads)}</cite></blockquote>
                ))}
                </div>
            ))}
          </div>
          <More total={s.objections.length} shown={allObj ? s.objections.length : Math.min(4, s.objections.length)} onClick={() => setAllObj(true)} noun="objections" />

          {s.angles.length > 0 && (
            <>
              <Sub>Angles</Sub>
              <div className="card flush angles">
                {(allAngles ? s.angles : s.angles.slice(0, 5)).map((a) => (
                  <div key={a.id} className="angle">
                    <div><div>{a.idea}</div><div className="xsmall faint">{personaName.get(a.persona) ?? a.persona}</div></div>
                    {market && <span className={`tag ${a.competitors_use_it ? "neutral" : "info"}`}>{a.competitors_use_it ? "Competitors use it" : "Nobody uses it"}</span>}
                  </div>
                ))}
              </div>
              <More total={s.angles.length} shown={allAngles ? s.angles.length : Math.min(5, s.angles.length)} onClick={() => setAllAngles(true)} noun="angles" />
            </>
          )}
        </div>
      )}
    </section>
  );
}

// ---------- launch ----------

const DECISION: Record<string, [string, string]> = {
  execute: ["ok", "Will launch"], needs_approval: ["warn", "Waiting for you"], simulated: ["sim", "Dry run"], refused: ["bad", "Refused"],
};

function Launch({ run, onRefresh }: { run: RunView; onRefresh: () => Promise<void> }) {
  const plan = run.plan;
  const decisions = new Map(run.launch.map((l) => [l.ad_set, l]));
  const ads = plan?.ad_sets.reduce((n, s) => n + s.ads.length, 0) ?? 0;
  return (
    <section id="launch" className="sec">
      <Head eyebrow="Launch" title="Your campaign, within your cap"
            text={plan ? `${plan.ad_sets.length} ad sets · ${ads} ads · ${eur(plan.daily_total_eur)}/day max · created paused.` : undefined} />
      {!plan ? (run.agency ? <AgencyPanel run={run} onRefresh={onRefresh} /> : <Waiting what="The plan comes after the test." />) : (
        <div className="stack" style={{ gap: 16 }}>
          {run.agency ? <AgencyPanel run={run} onRefresh={onRefresh} /> : run.status === "done" && <PublishPanel run={run} onRefresh={onRefresh} />}
          <div className="card flush scroll-x">
            <table className="table">
              <thead><tr><th>Audience</th><th>Who</th><th>Ads</th><th style={{ textAlign: "right" }}>Daily budget</th><th>Status</th></tr></thead>
              <tbody>
                {plan.ad_sets.map((s) => {
                  const d = decisions.get(s.name);
                  const [tag, text] = d ? DECISION[d.outcome] ?? ["neutral", d.outcome] : ["neutral", "—"];
                  return (
                    <tr key={s.name}>
                      <td style={{ fontWeight: 500 }}>{s.audience.name}</td>
                      <td className="small muted">{s.audience.countries.join(", ")} · {s.audience.age_min}–{s.audience.age_max}</td>
                      <td className="num">{s.ads.length}</td>
                      <td className="num mono" style={{ textAlign: "right" }}>{eur(s.daily_budget_eur)}</td>
                      <td><span className={`tag ${tag}`} title={d?.why}>{text}</span></td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot><tr><td colSpan={3} style={{ fontWeight: 600 }}>Total per day</td><td className="num mono" style={{ textAlign: "right", fontWeight: 600 }}>{eur(plan.daily_total_eur)} <span className="faint">of {eur(plan.daily_cap_eur)}</span></td><td /></tr></tfoot>
            </table>
          </div>
          {plan.errors.length > 0 && <div className="notice bad"><Alert /><span>{plan.errors.join("; ")}</span></div>}
          {plan.notes.length > 0 && <ul className="small muted notes">{plan.notes.map((n, i) => <li key={`${i}-${n}`}>{n}</li>)}</ul>}
        </div>
      )}
    </section>
  );
}
