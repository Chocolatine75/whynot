/**
 * The dashboard's data: every ad of every app, with its results, and what needs the owner's attention.
 *
 * Read from the run folders the engine writes: `agency/memory.json` (each ad the daily loop made: status, Meta id,
 * results day by day), `agency/reports/<day>.json` (what each day did), `agency/state.json` (account, approvals),
 * `plan.json` + `publish.json` (the campaign's static ads). Nothing is computed beyond sums, ratios and the
 * alert rules below; a simulated account is said so on every number it produced.
 */
import fs from "node:fs";
import path from "node:path";
import { type RunSummary, listRuns, runsRoot } from "./runs";
import { readAgency } from "./meta";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Json = Record<string, any>;

export interface Day { day: string; spend: number; impressions: number; clicks: number; conversions: number }
export interface Totals { spend: number; impressions: number; clicks: number; conversions: number; ctr: number | null; cpa: number | null }
export type AdStatus = "live" | "paused" | "proposed" | "rejected" | "failed" | "published" | "planned";

export interface AdRow {
  id: string; run: string; appName: string; icon: string | null; kind: "video" | "static";
  title: string; format: string; persona: string; status: AdStatus; launched: string | null;
  thumb: string | null; totals: Totals; days: Day[]; simulated: boolean; note: string | null;
}
export interface AppRow {
  run: string; appName: string; icon: string | null; status: RunSummary["status"]; account: string | null;
  simulated: boolean; live: number; ads: number; totals: Totals; days: Day[]; capEur: number | null; committedEur: number | null;
}
export type AlertLevel = "action" | "warn" | "info";
export interface Alert { level: AlertLevel; run: string; appName: string; title: string; detail: string; anchor: string }
export interface Crm { apps: AppRow[]; ads: AdRow[]; alerts: Alert[]; totals: Totals; days: Day[]; simulated: boolean }

const RULES = { minSpend: 20, fatigueDays: 3, fatigueDrop: 0.7, nearCap: 0.9, loginWarnDays: 10 };

/** Python writes NaN / Infinity (e.g. a cost per install with no install), which JSON.parse refuses: read them as null. */
function readJson(file: string): Json | null {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8").replace(/(?<=[:\[,]\s*)(-?Infinity|NaN)(?=\s*[,\]}])/g, "null")) as Json;
  } catch {
    return null;
  }
}

export function totals(days: Day[]): Totals {
  const t = days.reduce((a, d) => ({ spend: a.spend + d.spend, impressions: a.impressions + d.impressions, clicks: a.clicks + d.clicks,
    conversions: a.conversions + d.conversions }), { spend: 0, impressions: 0, clicks: 0, conversions: 0 });
  return { ...t, spend: Math.round(t.spend * 100) / 100, ctr: t.impressions ? t.clicks / t.impressions : null,
    cpa: t.conversions ? t.spend / t.conversions : null };
}

/** Day-by-day sums over several ads. */
export function sumDays(series: Day[][]): Day[] {
  const by = new Map<string, Day>();
  for (const s of series) for (const d of s) {
    const a = by.get(d.day) ?? { day: d.day, spend: 0, impressions: 0, clicks: 0, conversions: 0 };
    by.set(d.day, { day: d.day, spend: a.spend + d.spend, impressions: a.impressions + d.impressions, clicks: a.clicks + d.clicks, conversions: a.conversions + d.conversions });
  }
  return [...by.values()].sort((a, b) => a.day.localeCompare(b.day));
}

/** A live ad whose click rate over its last days fell well below its first days: people have seen it enough. */
export function fatigued(days: Day[], n = RULES.fatigueDays, drop = RULES.fatigueDrop): boolean {
  if (days.length < 2 * n) return false;
  const ctr = (ds: Day[]) => { const t = totals(ds); return t.ctr ?? 0; };
  const first = ctr(days.slice(0, n));
  return first > 0 && ctr(days.slice(-n)) < first * drop;
}

const toDay = (m: Json): Day => ({ day: String(m.day), spend: Number(m.spend_eur ?? 0), impressions: Number(m.impressions ?? 0),
  clicks: Number(m.clicks ?? 0), conversions: Number(m.conversions ?? 0) });

/** The video's poster next to it, as a path inside the run (never outside it). */
function posterFor(dir: string, file: string): string | null {
  const name = path.basename(file).replace(/\.mp4$/i, ".poster.jpg");
  return fs.existsSync(path.join(dir, "videos", name)) ? `videos/${name}` : null;
}

export function readCrm(root: string = runsRoot(), now = Date.now()): Crm {
  const apps: AppRow[] = [];
  const ads: AdRow[] = [];
  const alerts: Alert[] = [];
  for (const r of listRuns(root, now)) {
    const dir = path.join(root, r.id);
    const agency = readAgency(dir, now);
    const memory = readJson(path.join(dir, "agency", "memory.json"));
    const reportsDir = path.join(dir, "agency", "reports");
    const reports = fs.existsSync(reportsDir) ? fs.readdirSync(reportsDir).filter((n) => /^\d{4}-\d{2}-\d{2}\.json$/.test(n)).sort() : [];
    const latest = reports.length ? readJson(path.join(reportsDir, reports[reports.length - 1])) : null;
    const simulated = Boolean(latest?.simulated ?? agency?.simulated ?? false);
    const appAds: AdRow[] = [];
    const base = { run: r.id, appName: r.appName, icon: r.icon, simulated };
    const alert = (level: AlertLevel, title: string, detail: string, anchor = "launch") => alerts.push({ level, run: r.id, appName: r.appName, title, detail, anchor });

    // the daily loop's ads, with their results
    for (const [key, a] of Object.entries((memory?.ads ?? {}) as Json)) {
      if (a.status === "failed") continue;
      const days = (Array.isArray(a.metrics) ? a.metrics : []).map(toDay);
      const notes = Array.isArray(a.notes) ? a.notes.map(String) : [];
      const row: AdRow = { ...base, id: `${r.id}:${key}`, kind: "video", title: String(a.hook || key), format: String(a.format ?? ""),
        persona: String(a.persona ?? ""), status: a.status as AdStatus, launched: a.launched ?? null,
        thumb: a.file ? posterFor(dir, String(a.file)) : null, totals: totals(days), days, simulated, note: notes.at(-1) ?? null };
      appAds.push(row);
      if (row.status === "live" && row.totals.spend >= RULES.minSpend && row.totals.conversions === 0)
        alert("warn", `${row.title}: €${row.totals.spend.toFixed(0)} spent, no install`, "The agency pauses it if it stays like this.", "ads");
      if (row.status === "live" && fatigued(days))
        alert("warn", `${row.title}: click rate falling`, "People have seen it enough: a fresh ad takes its slot soon.", "ads");
    }

    // the campaign's static ads (results are read for the daily loop's ads only)
    const plan = readJson(path.join(dir, "plan.json"));
    const pub = readJson(path.join(dir, "publish.json"));
    const published = pub && Object.keys(pub.objects ?? {}).length > 0;
    for (const set of (plan?.ad_sets ?? []) as Json[]) for (const ad of (set.ads ?? []) as Json[]) {
      appAds.push({ ...base, id: `${r.id}:${ad.variant_id}`, kind: "static", title: String(ad.headline_on_image ?? ad.title ?? ""),
        format: "static", persona: String(set.audience?.name ?? ""), status: published ? (pub.status === "active" ? "live" : "published") : "planned",
        launched: null, thumb: ad.image_path ?? null, totals: totals([]), days: [], simulated, note: null });
    }

    // what needs the owner
    const waiting = new Set<string>((latest?.waiting_approval ?? []).map(String));
    if (agency?.waiting || waiting.size) alert("action", waiting.size ? `${waiting.size} ad${waiting.size > 1 ? "s wait" : " waits"} for your approval` : "The campaign waits for your approval",
      "Nothing goes live without it.");
    const login = agency?.account;
    if (login && login.daysLeft !== null && login.daysLeft < 0) alert("action", "Meta login expired", "Connect again on the Meta account page: the agency is stopped.");
    else if (login && login.daysLeft !== null && login.daysLeft < RULES.loginWarnDays) alert("warn", `Meta login ends in ${login.daysLeft} days`, "It renews by itself on the next run.");
    if (r.status === "failed") alert("action", "Stopped on an error", "Open the campaign to see why and try again.", "overview");
    for (const f of ((latest?.failures ?? []) as string[]).slice(0, 2)) alert("warn", "Something failed yesterday", f);
    for (const p of ((latest?.paused ?? []) as Json[]).slice(0, 3)) alert("info", `Paused ${p.ad}`, String(p.why ?? ""), "ads");
    const cap = Number(latest?.cap_eur ?? agency?.dailyCapEur ?? 0) || null;
    const committed = latest ? Number(latest.committed_eur ?? 0) : null;
    if (cap && committed !== null && committed >= cap * RULES.nearCap) alert("info", "At the daily cap", `€${committed.toFixed(0)} of €${cap.toFixed(0)} a day committed: new ads wait for a free slot.`);

    const days = sumDays(appAds.map((a) => a.days));
    apps.push({ ...base, status: r.status, account: login?.accountName ?? (simulated ? "Simulated account" : null), live: appAds.filter((a) => a.status === "live").length,
      ads: appAds.length, totals: totals(days), days, capEur: cap, committedEur: committed });
    ads.push(...appAds);
  }
  const order: Record<AlertLevel, number> = { action: 0, warn: 1, info: 2 };
  alerts.sort((a, b) => order[a.level] - order[b.level]);
  const days = sumDays(apps.map((a) => a.days));
  return { apps, ads, alerts, totals: totals(days), days, simulated: apps.some((a) => a.simulated && a.totals.impressions > 0) };
}
