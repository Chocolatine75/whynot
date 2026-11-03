"use client";
import { useEffect, useMemo, useState } from "react";
import type { PlanAd, Progress, RunView, Score, StageState, Variant } from "@/lib/runs";
import AppIcon from "@/components/AppIcon";
import PublishPanel from "@/components/PublishPanel";
import { Alert, ArrowRight, Shield } from "@/components/Icons";
import { STATUS_TAG, ago, eur, fileUrl, joinPhrases, signed, usd } from "@/lib/format";

const CTA_LABEL: Record<string, string> = {
  INSTALL_MOBILE_APP: "Install now", DOWNLOAD: "Download", USE_APP: "Use app", LEARN_MORE: "Learn more",
  SIGN_UP: "Sign up", SUBSCRIBE: "Subscribe",
};
const AVATAR = ["#0064e0", "#7a5cff", "#0a8cff", "#c74ae0", "#18794e", "#e8590c", "#0e7490", "#be185d"];
const avatarColor = (s: string) => AVATAR[[...s].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7) % AVATAR.length];
const initials = (s: string) => s.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
const VERDICT_TAG: Record<string, string> = { improved: "ok", "within noise": "neutral", worse: "bad", "not measured": "warn" };

type Section = { id: string; label: string; state?: StageState; count?: number };

export default function AgencyRoom({ initial }: { initial: RunView }) {
  const [run, setRun] = useState(initial);
  const refresh = async () => {
    const res = await fetch(`/api/run?id=${encodeURIComponent(run.id)}`, { cache: "no-store" });
    if (res.ok) setRun(await res.json());
  };
  useEffect(() => {
    if (run.status !== "running") return;
    const t = setInterval(refresh, 2500);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run.id, run.status]);

  const stage = (s: string) => run.stages.find((x) => x.stage === s)?.state;
  const scores = useMemo(() => {
    const out: Record<string, Score> = { ...(run.simulation?.scores ?? {}) };
    for (const g of run.evolution?.groups ?? []) for (const h of g.history) Object.assign(out, h.scores ?? {});
    return out;
  }, [run.simulation, run.evolution]);
  const variants = useMemo(() => new Map(run.variants.map((v) => [v.variant_id, v])), [run.variants]);
  const personas = useMemo(() => new Map(run.strategy?.personas.map((p) => [p.id, p.name]) ?? []), [run.strategy]);
  const brand = run.simulation?.brand ?? run.app?.name ?? "Your app";
  const adCount = run.plan?.ad_sets.reduce((n, s) => n + s.ads.length, 0) ?? 0;

  const sections: Section[] = [
    { id: "overview", label: "Overview" },
    { id: "market", label: "Market", state: stage("market"), count: run.marketAds.length || undefined },
    { id: "strategy", label: "Strategy", state: stage("strategy"), count: run.strategy?.personas.length },
    { id: "ads", label: "Ads", state: stage("produce"), count: adCount || undefined },
    ...(run.videos.length ? [{ id: "videos", label: "Videos", state: "done" as StageState, count: run.videos.length }] : []),
    { id: "test", label: "Simulated test", state: stage("simulate") },
    { id: "evolution", label: "Evolution", state: stage("evolve") },
    { id: "launch", label: "Launch", state: stage("plan") },
  ];
  const active = useScrollSpy(sections.map((s) => s.id));
  const [kind, label] = STATUS_TAG[run.status];
  const name = run.app?.name ?? run.config?.app_ref ?? "New campaign";

  return (
    <div className="room">
      <aside className="side" aria-label="Campaign sections">
        <div className="side-app">
          <AppIcon run={run.id} icon={run.icon} name={name} />
          <div style={{ minWidth: 0 }}>
            <div className="name">{name}</div>
            <span className={`tag dot ${kind}`} style={{ marginTop: 4 }}>{label}</span>
          </div>
        </div>
        <nav className="side-nav">
          {sections.map((s) => (
            <a key={s.id} href={`#${s.id}`} className={active === s.id ? "active" : undefined}>
              <span className={`state ${s.state === "cached" ? "done" : s.state ?? "done"}`} aria-hidden />
              {s.label}
              {s.count ? <span className="count">{s.count}</span> : null}
            </a>
          ))}
        </nav>
        <div className="side-foot">
          <div className="meter"><span>AI spend</span><strong>{usd(run.spentUsd)}</strong></div>
          <div className="meter"><span>Daily cap</span><strong>{eur(run.config?.daily_cap_eur ?? 0)}</strong></div>
          <p className="xsmall faint">Every model call is metered. Ad spend happens only after your approval.</p>
        </div>
      </aside>

      <main className="main">
        <Overview run={run} name={name} />
        <Market run={run} />
        <StrategySection run={run} />
        <Ads run={run} brand={brand} variants={variants} scores={scores} />
        {run.videos.length > 0 && <Videos run={run} personas={personas} />}
        <Test run={run} variants={variants} scores={scores} personas={personas} />
        <Evolution run={run} variants={variants} personas={personas} />
        <Launch run={run} onRefresh={refresh} />
      </main>
    </div>
  );
}

/** The section in view, for the side navigation. */
function useScrollSpy(ids: string[]) {
  const [active, setActive] = useState(ids[0]);
  const key = ids.join(",");
  useEffect(() => {
    const els = ids.map((id) => document.getElementById(id)).filter((e): e is HTMLElement => Boolean(e));
    const obs = new IntersectionObserver((entries) => {
      const seen = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (seen[0]) setActive(seen[0].target.id);
    }, { rootMargin: "-70px 0px -65% 0px" });
    els.forEach((e) => obs.observe(e));
    return () => obs.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return active;
}

function Head({ eyebrow, title, text, aside }: { eyebrow: string; title: string; text?: string; aside?: React.ReactNode }) {
  return (
    <div className="sec-head">
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

// ---------- overview ----------

function Overview({ run, name }: { run: RunView; name: string }) {
  const passed = run.variants.filter((v) => v.guards_passed).length;
  const pub = run.published;
  const stats: [string, string, string][] = [
    ["Competitor ads read", `${run.market?.ads ?? "—"}`, run.market ? `${run.market.competitors.length} competitors · Ad Library` : "Ad Library"],
    ["Customer profiles", `${run.strategy?.personas.length ?? "—"}`, "from reviews and the market"],
    ["Ads made", `${run.variants.length || "—"}`, run.variants.length ? `${passed} passed every check` : "statics"],
    ["Video ads", `${run.videos.length || "—"}`, "voiced, captioned, checked"],
    ["AI cost", usd(run.spentUsd), "real, metered"],
  ];
  return (
    <section id="overview" className="sec">
      <div className="hero">
        <AppIcon run={run.id} icon={run.icon} name={name} size="lg" />
        <div style={{ minWidth: 0 }}>
          <h1>{name}</h1>
          <div className="hero-meta">
            {run.app?.seller && <span>{run.app.seller}</span>}
            {run.app?.rating ? <span className="num">★ {run.app.rating.toFixed(1)} · {run.app.rating_count.toLocaleString("en")} ratings</span> : null}
            {run.config?.countries?.length ? <span>{run.config.countries.join(" · ")}</span> : null}
            {run.startedAt && <span>started {ago(run.startedAt)}</span>}
          </div>
        </div>
      </div>

      <div className="stack" style={{ marginTop: 28, gap: 20 }}>
        {pub && Object.keys(pub.objects).length > 0 ? (
          <div className="notice"><Shield /><div><strong>{pub.mode === "live" ? "On your Meta account" : "In the sandbox"}, {pub.status === "active" ? "running" : "paused"}.</strong>{" "}
            <span className="muted">Approved by {pub.approved_by ?? "—"}. One button in Launch pauses everything.</span></div></div>
        ) : (
          <div className="notice"><Shield /><div><strong>Nothing is live.</strong>{" "}
            <span className="muted">The campaign is prepared paused, within your {eur(run.config?.daily_cap_eur ?? 0)}/day cap, and waits for your approval.</span></div></div>
        )}
        <div className="stats">
          {stats.map(([l, v, d]) => (
            <div key={l} className="stat"><div className="eyebrow">{l}</div><div className="v">{v}</div><div className="d">{d}</div></div>
          ))}
        </div>
        <div className="card">
          <div className="spread" style={{ marginBottom: 16 }}>
            <h4>What the agency did</h4>
            <span className="small faint num">{run.stages.filter((s) => s.state === "done" || s.state === "cached").length} of {run.stages.length} steps</span>
          </div>
          <div className="pipeline">
            {run.stages.map((s) => (
              <div key={s.stage} className={`pipe ${s.state}`} title={s.error ?? s.label}>
                <div className="bar" />
                <span className="t">{s.label}</span>
                <span className="c">{s.usd > 0 ? usd(s.usd) : s.state === "skipped" ? "skipped" : s.state === "running" ? "working…" : ""}</span>
              </div>
            ))}
          </div>
          {run.stages.some((s) => s.error) && (
            <div className="notice bad" style={{ marginTop: 16 }}><Alert /><span>{run.stages.find((s) => s.error)?.error}</span></div>
          )}
        </div>
        {run.strategy?.positioning && (
          <div className="card pad-lg">
            <span className="eyebrow">Positioning</span>
            <p className="positioning" style={{ marginTop: 8 }}>{run.strategy.positioning}</p>
          </div>
        )}
      </div>
    </section>
  );
}

// ---------- market ----------

function Market({ run }: { run: RunView }) {
  const [who, setWho] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  const m = run.market;
  const names = new Map((m?.advertisers ?? []).map((a) => [a.page_id, a]));
  const ads = run.marketAds.filter((a) => !who || a.pageName === who);
  const shown = all ? ads : ads.slice(0, 9);
  const pages = [...new Set(run.marketAds.map((a) => a.pageName))].slice(0, 10);
  return (
    <section id="market" className="sec">
      <Head eyebrow="Research" title="Your market, from the Meta Ad Library"
            text={m ? `${m.competitors.length} competitors selling the same thing in ${m.research_countries.join(", ")}, ${m.ads} of their ads read. Longest-running first: an ad that runs for months is one that pays.` : undefined} />
      {!m ? <Waiting what="The scout is reading the Ad Library…" /> : (
        <div className="stack" style={{ gap: 18 }}>
          {pages.length > 1 && (
            <div className="seg" role="group" aria-label="Filter by advertiser">
              <button aria-pressed={who === null} onClick={() => setWho(null)}>All</button>
              {pages.map((p) => <button key={p} aria-pressed={who === p} onClick={() => setWho(p)}>{p}</button>)}
            </div>
          )}
          {run.marketAds.length === 0 ? (
            <div className="competitors">
              {m.competitors.map((c) => <span key={c.page_id} className="tag neutral">{names.get(c.page_id)?.page_name ?? c.page_id}</span>)}
            </div>
          ) : (
            <div className="ads-lib">
              {shown.map((a) => (
                <article key={a.id} className="lib-ad">
                  <div className="who">
                    <span className="avatar" style={{ background: avatarColor(a.pageName) }}>{initials(a.pageName)}</span>
                    <div style={{ minWidth: 0 }}>
                      <div className="small" style={{ fontWeight: 600 }}>{a.pageName}</div>
                      <div className="xsmall faint">Sponsored · {a.platforms.join(", ") || "Meta"}</div>
                    </div>
                  </div>
                  {a.body && <p className="body">{a.body}</p>}
                  {a.title && <p className="small" style={{ fontWeight: 600 }}>{a.title}</p>}
                  <div className="row" style={{ gap: 6 }}>
                    {a.days !== null && <span className={`tag ${a.days >= 60 ? "ok" : "neutral"} num`}>{a.days >= 60 ? "Long runner · " : ""}{a.days} days</span>}
                    {a.startDate && <span className="xsmall faint">since {a.startDate}</span>}
                  </div>
                </article>
              ))}
            </div>
          )}
          {ads.length > shown.length && <button className="btn secondary" style={{ alignSelf: "center" }} onClick={() => setAll(true)}>Show all {ads.length} ads</button>}
          <p className="xsmall faint">Searched for {m.terms.join(", ")} · {m.rejected.length} unrelated advertisers ignored.</p>
        </div>
      )}
    </section>
  );
}

// ---------- strategy ----------

function StrategySection({ run }: { run: RunView }) {
  const s = run.strategy;
  const objections = new Map(s?.objections.map((o) => [o.id, o]) ?? []);
  const personaName = new Map(s?.personas.map((p) => [p.id, p.name]) ?? []);
  return (
    <section id="strategy" className="sec">
      <Head eyebrow="Strategy · Muse Wonder" title="Who to talk to, and why they don't buy yet"
            text="Customer profiles worth their own ads. Every objection is quoted word for word from a review or a page, and checked against its source." />
      {!s ? <Waiting what="The strategist is reading the market and your reviews…" /> : (
        <div className="stack" style={{ gap: 28 }}>
          <div className="personas">
            {s.personas.map((p) => (
              <div key={p.id} className="card persona">
                <div className="who">
                  <span className="avatar" style={{ background: avatarColor(p.name), width: 40, height: 40 }}>{initials(p.name)}</span>
                  <div>
                    <h3>{p.name}</h3>
                    <div className="xsmall faint num">{p.age_min}–{p.age_max} · {p.gender === "all" ? "everyone" : p.gender} · {p.countries.join(" · ")}</div>
                  </div>
                </div>
                <p className="small muted">{p.description}</p>
                <dl className="kv">
                  <dt>Wants</dt><dd>{joinPhrases(p.motivations)}</dd>
                  <dt>Hesitates</dt><dd>{joinPhrases(p.objections.map((o) => objections.get(o)?.text ?? ""))}</dd>
                </dl>
              </div>
            ))}
          </div>

          <div>
            <h3 style={{ marginBottom: 12 }}>Why people say no</h3>
            <div className="objections">
              {s.objections.map((o) => (
                <div key={o.id} className="card stack" style={{ gap: 12 }}>
                  <h4>{o.text}</h4>
                  {o.evidence.slice(0, 2).map((e) => (
                    <blockquote key={e.ref + e.quote} className="quote">“{e.quote}”<cite>{e.ref.replace(":", " · ")}</cite></blockquote>
                  ))}
                  <p className="small"><span className="faint">The answer · </span>{o.answer}</p>
                </div>
              ))}
            </div>
          </div>

          {s.angles.length > 0 && (
            <div>
              <h3 style={{ marginBottom: 12 }}>Angles</h3>
              <div className="card flush angles">
                {s.angles.map((a) => (
                  <div key={a.id} className="angle">
                    <div><div>{a.idea}</div><div className="xsmall faint">{personaName.get(a.persona) ?? a.persona}</div></div>
                    <span className={`tag ${a.competitors_use_it ? "neutral" : "info"}`}>{a.competitors_use_it ? "Competitors use it" : "Nobody uses it"}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

// ---------- ads ----------

function Post({ run, brand, ad, variant, score }: { run: RunView; brand: string; ad: PlanAd; variant?: Variant; score?: Score }) {
  return (
    <article className="post">
      <div className="post-head">
        <AppIcon run={run.id} icon={run.icon} name={brand} size="sm" />
        <div><div className="n">{brand}</div><div className="s">Sponsored</div></div>
      </div>
      <p className="post-text">{ad.body}</p>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={fileUrl(run.id, ad.image_path)} alt={ad.headline_on_image} loading="lazy" />
      <div className="post-cta">
        <span className="t">{ad.title}</span>
        <span className="b">{CTA_LABEL[ad.cta] ?? ad.cta}</span>
      </div>
      <div className="post-foot">
        {score ? <>
          <span className="tag sim">Simulated</span>
          <span className="small num">{signed(score.lift_over_placebo)} vs placebo</span>
          <span className="small faint num">intent {score.intent.toFixed(1)}/5</span>
        </> : <span className="tag neutral">Not tested</span>}
        {(variant?.generation ?? 0) > 0 && <span className="tag info">Evolved · gen {variant!.generation}</span>}
        {variant?.guards_passed && <span className="tag ok" title="The app's pixels are identical to its store screenshot">Real screen</span>}
        {score?.top_why_not?.[0] && <p className="obj">“{score.top_why_not[0]}”</p>}
      </div>
    </article>
  );
}

function Ads({ run, brand, variants, scores }: { run: RunView; brand: string; variants: Map<string, Variant>; scores: Record<string, Score> }) {
  const sets = run.plan?.ad_sets ?? [];
  const [pick, setPick] = useState(0);
  const set = sets[Math.min(pick, sets.length - 1)];
  return (
    <section id="ads" className="sec">
      <Head eyebrow="Creative" title="The ads, one set per customer profile"
            text="Composed in code around your real app screens, cut out by SAM 3.1 and never generated. Shown as they appear in the feed."
            aside={<span className="tag sim">Scores are simulated</span>} />
      {!set ? <Waiting what="The creative director is writing concepts…" /> : (
        <div className="stack" style={{ gap: 18 }}>
          {sets.length > 1 && (
            <div className="seg" role="group" aria-label="Audience">
              {sets.map((s, i) => <button key={s.name} aria-pressed={i === pick} onClick={() => setPick(i)}>{s.audience.name}</button>)}
            </div>
          )}
          <p className="small muted">{set.audience.countries.join(" · ")} · {set.audience.age_min}–{set.audience.age_max} · {eur(set.daily_budget_eur)}/day</p>
          <div className="posts">
            {set.ads.map((ad) => <Post key={ad.variant_id} run={run} brand={brand} ad={ad} variant={variants.get(ad.variant_id)} score={scores[ad.variant_id]} />)}
          </div>
        </div>
      )}
    </section>
  );
}

// ---------- videos ----------

function Videos({ run, personas }: { run: RunView; personas: Map<string, string> }) {
  return (
    <section id="videos" className="sec">
      <Head eyebrow="Video ads · Muse Image, SAM 3.1, Voice Transcribe" title="Short videos on what's trending"
            text="A skit on a trending format, your real app animated in the phone, voices and captions. Every final mix is transcribed back and loudness-checked before it ships." />
      <div className="reels">
        {run.videos.map((v) => (
          <article key={v.path} className="reel">
            <div className="phone">
              <video src={fileUrl(run.id, v.path)} poster={v.poster ? fileUrl(run.id, v.poster) : undefined} controls playsInline preload="none" />
            </div>
            <div className="row" style={{ gap: 6 }}>
              {v.tone && <span className="tag info">{v.tone}</span>}
              <span className="tag neutral num">{Math.round(v.seconds)} s</span>
              {v.wordErrorRate !== null && (
                <span className={`tag ${v.flags.length ? "warn" : "ok"}`} title={v.flags.join("; ") || "The transcription of the final mix matches the captions"}>
                  {v.flags.length ? `${v.flags.length} QA flag${v.flags.length > 1 ? "s" : ""}` : "Checked by ear"}
                </span>
              )}
            </div>
            <p className="hook">{v.hook}</p>
            <p className="why">{v.why}</p>
            <p className="xsmall faint">{personas.get(v.persona) ?? v.persona}{v.lufs !== null && ` · ${v.lufs.toFixed(1)} LUFS`}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

// ---------- simulated test ----------

function LiftBar({ value, max }: { value: number; max: number }) {
  const w = Math.min(50, (Math.abs(value) / (max || 1)) * 50);
  return (
    <div className="lift">
      <div className="track"><div className={`fill${value < 0 ? " neg" : ""}`} style={value >= 0 ? { left: "50%", width: `${w}%` } : { right: "50%", width: `${w}%` }} /></div>
      <span className="num mono small" style={{ width: 44, textAlign: "right" }}>{signed(value)}</span>
    </div>
  );
}

function Test({ run, variants, scores, personas }: { run: RunView; variants: Map<string, Variant>; scores: Record<string, Score>; personas: Map<string, string> }) {
  const sim = run.simulation;
  const groups = sim?.groups ?? [];
  const [pick, setPick] = useState(0);
  const g = groups[Math.min(pick, groups.length - 1)];
  const rows = g ? run.variants.filter((v) => v.persona === g.persona && v.language === g.language && scores[v.variant_id] && (v.generation ?? 0) === 0)
    .map((v) => ({ v, s: scores[v.variant_id] })).sort((a, b) => b.s.lift_over_placebo - a.s.lift_over_placebo) : [];
  const max = Math.max(1, ...rows.map((r) => Math.abs(r.s.lift_over_placebo)));
  const whyNot = [...new Set(rows.flatMap((r) => r.s.top_why_not.slice(0, 1)))].slice(0, 6);
  return (
    <section id="test" className="sec">
      <Head eyebrow="Simulated feed · viewer agents on Muse Spark Open" title="Tested before a cent is spent"
            text="Each ad is dropped into a feed of your competitors' real ads. Viewer agents built from your customer profiles say what they noticed, what they believed and why they wouldn't buy. A placebo ad checks the test itself."
            aside={<span className="tag sim">Simulated, not real behaviour</span>} />
      {!sim ? <Waiting what="Waiting for the ads to be made…" /> : !sim.simulated ? (
        <div className="notice"><Alert /><span>Not simulated for this app: {sim.reason ?? "no competitor ads to test against."}</span></div>
      ) : (
        <div className="stack" style={{ gap: 18 }}>
          {groups.length > 1 && (
            <div className="seg" role="group" aria-label="Audience">
              {groups.map((x, i) => <button key={x.persona + x.language} aria-pressed={i === pick} onClick={() => setPick(i)}>{personas.get(x.persona) ?? x.persona} · {x.language}</button>)}
            </div>
          )}
          <div className="card flush scroll-x">
            <table className="board">
              <thead><tr><th>Ad</th><th /><th>Lift vs placebo</th><th className="r">Intent</th><th className="r">Views</th></tr></thead>
              <tbody>
                {rows.map(({ v, s }) => (
                  <tr key={v.variant_id}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <td style={{ width: 60 }}>{v.image && <img className="thumb" src={fileUrl(run.id, v.image)} alt="" loading="lazy" />}</td>
                    <td style={{ minWidth: 200 }}><div style={{ fontWeight: 500 }}>{v.texts?.hook ?? v.template_id}</div><div className="xsmall faint">{v.template_id.replace(/_/g, " ")}</div></td>
                    <td><LiftBar value={s.lift_over_placebo} max={max} /></td>
                    <td className="r num mono small">{s.intent.toFixed(1)}</td>
                    <td className="r num mono small">{s.views}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {whyNot.length > 0 && (
            <div>
              <h3 style={{ marginBottom: 12 }}>Why not, in the viewers' words</h3>
              <div className="whynot">{whyNot.map((w) => <div key={w} className="card">“{w}”</div>)}</div>
            </div>
          )}
          <p className="xsmall faint">Lift: how much more often viewers picked the ad than the placebo, in the same feeds. Intent on a 1–5 scale. These are simulated reactions; their reliability is measured on the Validation page.</p>
        </div>
      )}
    </section>
  );
}

// ---------- evolution ----------

function ProgressChart({ points }: { points: Progress[] }) {
  const W = 520, H = 180, P = 28;
  const lo = Math.min(...points.flatMap((p) => [p.ci?.[0] ?? p.strength, p.placebo ?? p.strength]), 0);
  const hi = Math.max(...points.flatMap((p) => [p.ci?.[1] ?? p.strength]), 1);
  const x = (i: number) => P + (i * (W - 2 * P)) / Math.max(1, points.length - 1);
  const y = (v: number) => H - P - ((v - lo) / (hi - lo || 1)) * (H - 2 * P);
  const placebo = points.filter((p) => typeof p.placebo === "number");
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Strength of the best ad per generation, with confidence intervals">
      <line className="axis" x1={P} x2={W - P} y1={H - P} y2={H - P} />
      {placebo.length > 1 && <polyline className="placebo" points={placebo.map((p) => `${x(points.indexOf(p))},${y(p.placebo!)}`).join(" ")} />}
      {points.map((p, i) => p.ci && <line key={`ci${i}`} className="ci" x1={x(i)} x2={x(i)} y1={y(p.ci[0])} y2={y(p.ci[1])} />)}
      <polyline className="line" points={points.map((p, i) => `${x(i)},${y(p.strength)}`).join(" ")} />
      {points.map((p, i) => <circle key={i} className="pt" cx={x(i)} cy={y(p.strength)} r={4.5} />)}
      {points.map((p, i) => <text key={`t${i}`} x={x(i)} y={H - 8} textAnchor="middle">gen {p.generation}</text>)}
    </svg>
  );
}

function Evolution({ run, variants, personas }: { run: RunView; variants: Map<string, Variant>; personas: Map<string, string> }) {
  const groups = run.evolution?.groups ?? [];
  return (
    <section id="evolution" className="sec">
      <Head eyebrow="Evolution" title="How the ads got better"
            text="Each round the agents change one element of the best ads to answer what viewers objected to, then the generation meets its parents, the original champion and a placebo head to head. A gain only counts above the measured noise."
            aside={<span className="tag sim">Simulated</span>} />
      {groups.length === 0 ? <Waiting what={run.evolution?.skipped ?? "Evolution runs after the simulated test."} /> : (
        <div className="stack" style={{ gap: 16 }}>
          {groups.map((g) => {
            const chain: Variant[] = [];
            let id: string | null | undefined = g.champion;
            while (id && variants.get(id) && chain.length < 8) { chain.unshift(variants.get(id)!); id = variants.get(id)!.parent_id; }
            return (
              <div key={g.persona + g.language} className="card pad-lg stack" style={{ gap: 20 }}>
                <div className="spread">
                  <h3>{personas.get(g.persona) ?? g.persona} <span className="faint small">· {g.language}</span></h3>
                  {g.result && (
                    <span className={`tag ${VERDICT_TAG[g.result.verdict] ?? "neutral"}`}>
                      gen {g.result.generation} vs gen 0: {signed(g.result.difference)}{g.result.noise_floor !== null && ` (noise ±${g.result.noise_floor.toFixed(2)})`} · {g.result.verdict}
                    </span>
                  )}
                </div>
                {g.progress && g.progress.length > 1 && <ProgressChart points={g.progress} />}
                {chain.length > 0 && (
                  <div className="lineage">
                    {chain.map((v, i) => (
                      <div key={v.variant_id} className="row" style={{ flexWrap: "nowrap", alignItems: "flex-start", gap: 12 }}>
                        {i > 0 && <ArrowRight className="gen-arrow" />}
                        <div className="gen">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          {v.image && <img src={fileUrl(run.id, v.image)} alt={v.texts?.hook ?? ""} loading="lazy" />}
                          <span className="eyebrow">{(v.generation ?? 0) === 0 ? "Original" : `Generation ${v.generation}`}</span>
                          {v.mutation
                            ? <p className="small">Changed the <strong>{v.mutation.gene}</strong>: “{v.mutation.text}”<span className="faint" style={{ display: "block", marginTop: 4 }}>{v.mutation.why}</span></p>
                            : <p className="small muted">{v.texts?.hook}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

// ---------- launch ----------

function Launch({ run, onRefresh }: { run: RunView; onRefresh: () => Promise<void> }) {
  const plan = run.plan;
  const decisions = new Map(run.launch.map((l) => [l.ad_set, l]));
  return (
    <section id="launch" className="sec">
      <Head eyebrow="Launch" title="Your campaign, within your cap"
            text="One ad set per profile. Created paused on Meta; nothing delivers until you approve, and Meta keeps handling bidding and delivery." />
      {!plan ? <Waiting what="The plan comes after the test." /> : (
        <div className="stack" style={{ gap: 16 }}>
          <div className="card flush scroll-x">
            <table className="table">
              <thead><tr><th>Audience</th><th>Who</th><th>Ads</th><th style={{ textAlign: "right" }}>Daily budget</th><th>Decision</th></tr></thead>
              <tbody>
                {plan.ad_sets.map((s) => {
                  const d = decisions.get(s.name);
                  const tag = d?.outcome === "execute" ? "ok" : d?.outcome === "needs_approval" ? "warn" : d?.outcome === "simulated" ? "sim" : "neutral";
                  return (
                    <tr key={s.name}>
                      <td style={{ fontWeight: 500 }}>{s.audience.name}</td>
                      <td className="small muted">{s.audience.countries.join(" · ")} · {s.audience.age_min}–{s.audience.age_max}</td>
                      <td className="num">{s.ads.length}</td>
                      <td className="num mono" style={{ textAlign: "right" }}>{eur(s.daily_budget_eur)}</td>
                      <td><span className={`tag ${tag}`} title={d?.why}>{d?.outcome?.replace("_", " ") ?? "—"}</span></td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot><tr><td colSpan={3} style={{ fontWeight: 600 }}>Total per day</td><td className="num mono" style={{ textAlign: "right", fontWeight: 600 }}>{eur(plan.daily_total_eur)} <span className="faint">/ {eur(plan.daily_cap_eur)}</span></td><td /></tr></tfoot>
            </table>
          </div>
          {plan.errors.length > 0 && <div className="notice bad"><Alert /><span>{plan.errors.join("; ")}</span></div>}
          {plan.notes.length > 0 && (
            <ul className="small muted" style={{ margin: 0, paddingLeft: 18 }}>{plan.notes.map((n) => <li key={n}>{n}</li>)}</ul>
          )}
          {run.status === "done" && <PublishPanel run={run} onRefresh={onRefresh} />}
        </div>
      )}
    </section>
  );
}
