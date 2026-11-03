"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import type { AdRow, AdStatus, Alert, Crm, Day } from "@/lib/crm";
import AppIcon from "@/components/AppIcon";
import { Alert as AlertIcon, Chevron } from "@/components/Icons";
import { eur, fileUrl, runUrl } from "@/lib/format";

const STATUS: Record<AdStatus, [string, string]> = {
  live: ["ok", "Live"], paused: ["neutral", "Paused"], proposed: ["warn", "Waiting for you"], published: ["info", "On Meta, paused"],
  planned: ["neutral", "Planned"], rejected: ["bad", "Rejected"], failed: ["bad", "Failed"],
};
const FILTERS: [string, string, (a: AdRow) => boolean][] = [
  ["all", "All", () => true], ["live", "Live", (a) => a.status === "live"], ["waiting", "Waiting", (a) => a.status === "proposed"],
  ["paused", "Paused", (a) => a.status === "paused" || a.status === "published"], ["planned", "Planned", (a) => a.status === "planned"],
];
type SortKey = "spend" | "impressions" | "clicks" | "ctr" | "conversions" | "cpa" | "launched";
const pct = (x: number | null) => (x === null ? "—" : `${(x * 100).toFixed(2)} %`);
const int = (x: number) => x.toLocaleString("en");
const money = (x: number | null) => (x === null ? "—" : eur(Math.round(x * 100) / 100));

/** A small line of daily values; flat and quiet when there is nothing yet. */
export function Spark({ days, pick, w = 96, h = 28 }: { days: Day[]; pick: (d: Day) => number; w?: number; h?: number }) {
  if (days.length < 2) return <svg width={w} height={h} className="spark flat" aria-hidden><line x1={0} x2={w} y1={h - 2} y2={h - 2} /></svg>;
  const v = days.map(pick);
  const max = Math.max(...v, 1e-9);
  const pts = v.map((x, i) => `${(i / (v.length - 1)) * w},${h - 2 - (x / max) * (h - 4)}`).join(" ");
  return (
    <svg width={w} height={h} className="spark" aria-hidden>
      <polyline points={`0,${h} ${pts} ${w},${h}`} className="area" />
      <polyline points={pts} className="stroke" />
    </svg>
  );
}

function AlertRow({ a }: { a: Alert }) {
  return (
    <Link href={`${runUrl(a.run)}#${a.anchor}`} className={`alert ${a.level}`}>
      <AlertIcon />
      <div style={{ minWidth: 0 }}>
        <div className="a-title">{a.title}</div>
        <div className="xsmall faint">{a.appName} · {a.detail}</div>
      </div>
      <Chevron className="chev" />
    </Link>
  );
}

export default function Dashboard({ crm }: { crm: Crm }) {
  // an app run twice shows the day of each campaign, so the two can be told apart
  const short = (n: string) => n.split(/[:–-]/)[0].trim();
  const twice = new Set(crm.apps.map((a) => short(a.appName)).filter((n, i, all) => all.indexOf(n) !== i));
  const appLabel = (a: { appName: string; run: string }) => twice.has(short(a.appName)) ? `${short(a.appName)} · ${(([, , mo, d, h, mi]) => (d ? `${d}/${mo} ${h}:${mi}` : ""))(/(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})/.exec(a.run) ?? [])}` : short(a.appName);
  const [app, setApp] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "spend", desc: true });

  const rows = useMemo(() => {
    const f = FILTERS.find((x) => x[0] === filter)![2];
    const needle = q.trim().toLowerCase();
    const value = (a: AdRow): number => sort.key === "launched" ? Date.parse(a.launched ?? "") || 0
      : sort.key === "ctr" ? a.totals.ctr ?? -1 : sort.key === "cpa" ? a.totals.cpa ?? Infinity : a.totals[sort.key];
    return crm.ads.filter((a) => (!app || a.run === app) && f(a) && (!needle || `${a.title} ${a.format} ${a.persona} ${a.appName}`.toLowerCase().includes(needle)))
      .sort((a, b) => (sort.desc ? value(b) - value(a) : value(a) - value(b)));
  }, [crm.ads, app, filter, q, sort]);

  const scope = app ? crm.apps.filter((a) => a.run === app) : crm.apps;
  const t = app ? scope[0]?.totals ?? crm.totals : crm.totals;
  const days = app ? scope[0]?.days ?? [] : crm.days;
  const alerts = app ? crm.alerts.filter((a) => a.run === app) : crm.alerts;
  const live = scope.reduce((n, a) => n + a.live, 0);
  const kpis: [string, string, (d: Day) => number][] = [
    ["Spend", money(t.spend), (d) => d.spend], ["Impressions", int(t.impressions), (d) => d.impressions],
    ["Clicks", int(t.clicks), (d) => d.clicks], ["Click rate", pct(t.ctr), (d) => (d.impressions ? d.clicks / d.impressions : 0)],
    ["Installs", int(t.conversions), (d) => d.conversions], ["Cost per install", money(t.cpa), (d) => (d.conversions ? d.spend / d.conversions : 0)],
  ];
  const th = (key: SortKey, label: string) => (
    <th className="r"><button className={`sort${sort.key === key ? " on" : ""}`} onClick={() => setSort({ key, desc: sort.key === key ? !sort.desc : true })}>
      {label}{sort.key === key ? (sort.desc ? " ↓" : " ↑") : ""}</button></th>
  );

  return (
    <main className="page wide" id="content">
      <div className="page-head">
        <div>
          <h1>Dashboard</h1>
          <p>Every ad the agency runs, for every app, with what needs you first.</p>
        </div>
        <div className="row" style={{ gap: 8 }}>
          {crm.simulated && <span className="tag sim" title="Results from the simulated account are invented by the engine for demos and tests">Includes a simulated account</span>}
          <Link href="/" className="btn">New campaign</Link>
        </div>
      </div>

      <div className="seg" role="group" aria-label="App" style={{ marginBottom: 16 }}>
        <button aria-pressed={app === null} onClick={() => setApp(null)}>All apps</button>
        {crm.apps.map((a) => <button key={a.run} aria-pressed={app === a.run} onClick={() => setApp(a.run)}>{appLabel(a)}</button>)}
      </div>

      <div className="kpis">
        {kpis.map(([label, v, pick]) => (
          <div key={label} className="kpi">
            <span className="label">{label}</span>
            <span className="v">{v}</span>
            <Spark days={days} pick={pick} w={120} />
          </div>
        ))}
      </div>

      <div className="dash-grid">
        <section className="card flush" aria-labelledby="alerts-h">
          <div className="panel-head"><h2 id="alerts-h" className="h4">Needs you</h2><span className="tag neutral num">{alerts.length}</span></div>
          {alerts.length === 0 ? <p className="empty small">Nothing to do. The agency is on it.</p> : (
            <div className="alerts">{alerts.slice(0, 8).map((a, i) => <AlertRow key={`${i}-${a.title}`} a={a} />)}</div>
          )}
        </section>
        <section className="card flush" aria-labelledby="apps-h">
          <div className="panel-head"><h2 id="apps-h" className="h4">Apps</h2><span className="small faint">{live} live ads</span></div>
          <div className="apps">
            {crm.apps.map((a) => (
              <div key={a.run} className={`app-row${app === a.run ? " on" : ""}`}>
                <button className="app-pick" onClick={() => setApp(app === a.run ? null : a.run)} aria-pressed={app === a.run}>
                  <AppIcon run={a.run} icon={a.icon} name={a.appName} size="sm" />
                  <span className="app-name">{appLabel(a)}</span>
                </button>
                <span className="small num">{a.live} live</span>
                <span className="small num mono">{money(a.totals.spend)}</span>
                <span className="small num">{pct(a.totals.ctr)}</span>
                <Spark days={a.days} pick={(d) => d.spend} w={72} h={22} />
                <Link href={runUrl(a.run)} className="small" aria-label={`Open ${a.appName}`}>Open</Link>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="card flush" style={{ marginTop: 16 }} aria-labelledby="ads-h">
        <div className="panel-head wrap">
          <h2 id="ads-h" className="h4">Ads <span className="faint num">{rows.length}</span></h2>
          <div className="row" style={{ gap: 8 }}>
            <div className="seg" role="group" aria-label="Status">
              {FILTERS.map(([id, label]) => <button key={id} aria-pressed={filter === id} onClick={() => setFilter(id)}>{label}</button>)}
            </div>
            <input className="input" placeholder="Search ads" aria-label="Search ads" value={q} onChange={(e) => setQ(e.target.value)} style={{ width: 200, height: 36 }} />
          </div>
        </div>
        <div className="scroll-x">
          <table className="board ads-table">
            <thead><tr>
              <th>Ad</th><th>Status</th>{th("launched", "Launched")}{th("spend", "Spend")}{th("impressions", "Impr.")}{th("clicks", "Clicks")}
              {th("ctr", "CTR")}{th("conversions", "Installs")}{th("cpa", "Per install")}<th>Trend</th>
            </tr></thead>
            <tbody>
              {rows.length === 0 && <tr><td colSpan={10} className="empty small">No ad matches.</td></tr>}
              {rows.map((a) => {
                const [tag, label] = STATUS[a.status] ?? ["neutral", a.status];
                return (
                  <tr key={a.id}>
                    <td>
                      <Link href={`${runUrl(a.run)}#${a.kind === "video" ? "videos" : "ads"}`} className="ad-cell">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        {a.thumb ? <img className={`thumb${a.kind === "video" ? " tall" : ""}`} src={fileUrl(a.run, a.thumb)} alt="" loading="lazy" /> : <span className="thumb blank" />}
                        <span style={{ minWidth: 0 }}>
                          <span className="ad-title">{a.title}</span>
                          <span className="xsmall faint">{appLabel(a)} · {a.kind === "video" ? a.format : "static"}{a.persona ? ` · ${a.persona.replace(/_/g, " ")}` : ""}</span>
                        </span>
                      </Link>
                    </td>
                    <td><span className={`tag ${tag}`} title={a.note ?? undefined}>{label}</span>{a.simulated && a.days.length > 0 && <span className="tag sim" style={{ marginLeft: 4 }}>sim</span>}</td>
                    <td className="r small num">{a.launched ?? "—"}</td>
                    <td className="r mono small">{a.days.length ? money(a.totals.spend) : "—"}</td>
                    <td className="r small num">{a.days.length ? int(a.totals.impressions) : "—"}</td>
                    <td className="r small num">{a.days.length ? int(a.totals.clicks) : "—"}</td>
                    <td className="r small num">{pct(a.totals.ctr)}</td>
                    <td className="r small num">{a.days.length ? a.totals.conversions : "—"}</td>
                    <td className="r mono small">{money(a.totals.cpa)}</td>
                    <td><Spark days={a.days} pick={(d) => (d.impressions ? d.clicks / d.impressions : 0)} w={80} h={22} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
      <p className="xsmall faint" style={{ marginTop: 12 }}>Results come from Meta (Insights), day by day, for the ads the agency launched; the campaign&apos;s static ads show their status only. Trend: click rate per day.</p>
    </main>
  );
}
