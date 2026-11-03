/**
 * Read `whynot create` run folders for the client platform.
 *
 * A run folder is written by the Python engine (src/whynot/agency/create.py): JSON per stage, an
 * append-only events.jsonl, ads/*.png. This module only reads it. Every path is resolved inside the
 * runs root; anything that escapes it is refused.
 */
import fs from "node:fs";
import path from "node:path";
import { type AgencyView, readAgency } from "./meta";

export const STAGES = ["app", "market", "strategy", "creative", "produce", "simulate", "evolve", "plan", "report"] as const;
export type Stage = (typeof STAGES)[number];
export type StageState = "pending" | "running" | "done" | "cached" | "error" | "skipped";

export const STAGE_LABELS: Record<Stage, string> = {
  app: "Reading the App Store page",
  market: "Researching competitors",
  strategy: "Writing the strategy",
  creative: "Creating ad concepts",
  produce: "Producing the ads",
  simulate: "Testing in a simulated feed",
  evolve: "Evolving the best ads",
  plan: "Planning the campaign",
  report: "Writing the report",
};

export const REPO_ROOT = path.resolve(process.env.WHYNOT_REPO ?? path.join(process.cwd(), ".."));
export function runsRoot(): string {
  return path.resolve(process.env.WHYNOT_RUNS_DIR ?? path.join(REPO_ROOT, "outputs", "runs"));
}

export class RunPathError extends Error {}

/** A run id is its folder path relative to the runs root, with "/" kept (e.g. "generic/20261029-...-id123"). */
export function resolveRun(id: string, root: string = runsRoot()): string {
  if (!id || id.includes("\0") || path.isAbsolute(id)) throw new RunPathError("bad run id");
  const dir = path.resolve(root, id);
  if (dir !== root && !dir.startsWith(root + path.sep)) throw new RunPathError("run id escapes the runs folder");
  if (!fs.existsSync(path.join(dir, "config.json"))) throw new RunPathError("no such run");
  // the lexical check is not enough: a symlink inside the root could point anywhere
  const realRoot = fs.realpathSync(root);
  const realDir = fs.realpathSync(dir);
  if (!realDir.startsWith(realRoot + path.sep)) throw new RunPathError("run folder resolves outside the runs folder");
  return dir;
}

const SERVABLE = new Map([[".png", "image/png"], [".jpg", "image/jpeg"], [".jpeg", "image/jpeg"], [".mp4", "video/mp4"],
  [".md", "text/markdown; charset=utf-8"]]);

/** A file inside a run that the browser may load (ad images, screenshots, video ads, the report). */
export function resolveRunFile(id: string, rel: string, root: string = runsRoot()): { file: string; type: string } {
  const dir = resolveRun(id, root);
  if (!rel || rel.includes("\0") || path.isAbsolute(rel)) throw new RunPathError("bad file path");
  const file = path.resolve(dir, rel);
  if (!file.startsWith(dir + path.sep)) throw new RunPathError("file escapes the run folder");
  const type = SERVABLE.get(path.extname(file).toLowerCase());
  if (!type) throw new RunPathError("file type not served");
  if (!fs.existsSync(file) || !fs.statSync(file).isFile()) throw new RunPathError("no such file");
  const realDir = fs.realpathSync(dir);
  if (!fs.realpathSync(file).startsWith(realDir + path.sep)) throw new RunPathError("file resolves outside the run folder");
  return { file, type };
}

function readJson<T>(dir: string, name: string): T | null {
  const p = path.join(dir, name);
  if (!fs.existsSync(p)) return null;
  try {
    return JSON.parse(fs.readFileSync(p, "utf8")) as T;
  } catch {
    return null; // a stage may be writing it right now
  }
}

export interface RunEvent { ts: string; stage: string; status: string; usd?: number; seconds?: number; error?: string }

export function readEvents(dir: string): RunEvent[] {
  const p = path.join(dir, "events.jsonl");
  if (!fs.existsSync(p)) return [];
  return fs.readFileSync(p, "utf8").split("\n").filter(Boolean).flatMap((line) => {
    try { return [JSON.parse(line) as RunEvent]; } catch { return []; }
  });
}

export interface StageView { stage: Stage; label: string; state: StageState; usd: number; seconds?: number; error?: string }

/** Stage states from the event log: the latest event per stage wins; a "redo" resets later stages. */
export function stageStates(events: RunEvent[]): StageView[] {
  const last = new Map<string, RunEvent>();
  const spent = new Map<string, number>();
  for (const e of events) {
    if (e.status === "redo") {
      const from = STAGES.indexOf(e.stage as Stage);
      for (const s of STAGES.slice(Math.max(0, from))) last.delete(s);
      continue;
    }
    last.set(e.stage, e);
    if (e.status === "ok" || e.status === "error") spent.set(e.stage, (spent.get(e.stage) ?? 0) + (e.usd ?? 0));
  }
  const views = STAGES.map((stage): StageView => {
    const e = last.get(stage);
    const state: StageState = !e ? "pending" : e.status === "start" ? "running" : e.status === "ok" ? "done"
      : e.status === "cached" ? "cached" : e.status === "error" ? "error" : "pending";
    return { stage, label: STAGE_LABELS[stage], state, usd: spent.get(stage) ?? 0, seconds: e?.seconds, error: e?.error };
  });
  // a finished run made before a stage existed (or that skipped it): pending stages before the end were skipped
  const finished = ["done", "cached"].includes(views[views.length - 1].state);
  return finished ? views.map((v) => (v.state === "pending" ? { ...v, state: "skipped" } : v)) : views;
}

export function totalSpent(events: RunEvent[]): number {
  return events.reduce((sum, e) => sum + (e.status === "ok" || e.status === "error" ? e.usd ?? 0 : 0), 0);
}

export type RunStatus = "running" | "done" | "failed" | "stopped";

export function runStatus(stages: StageView[], lastEventAt: number | null, now = Date.now()): RunStatus {
  if (stages.some((s) => s.state === "error")) return "failed";
  if (stages.every((s) => s.state === "done" || s.state === "cached" || s.state === "skipped")) return "done";
  const quiet = lastEventAt === null || now - lastEventAt > 15 * 60_000; // no event for 15 min: the process is gone
  return quiet ? "stopped" : "running";
}

// --- the shapes the engine writes (only the fields the platform uses) --------------------------------

export interface App { app_id: string; name: string; seller: string; store_url: string; rating: number | null; rating_count: number; genres: string[]; reviews: { id: string }[] }
export interface Evidence { ref: string; quote: string }
export interface Strategy {
  positioning: string;
  personas: { id: string; name: string; description: string; age_min: number; age_max: number; gender: string; countries: string[]; motivations: string[]; objections: string[] }[];
  objections: { id: string; text: string; answer: string; evidence: Evidence[] }[];
  angles: { id: string; idea: string; persona: string; competitors_use_it: boolean }[];
  claims: { id: string; text: string }[];
  notes: string[];
}
export interface Variant {
  variant_id: string; template_id: string; persona: string; language: string; generation?: number; parent_id?: string;
  image?: string; guards_passed: boolean; texts?: Record<string, string>; mutation?: { gene: string; text: string; why: string };
}
export interface Score { lift: number; lift_over_placebo: number; intent: number; intent_vs_placebo: number; views: number; top_why_not: string[]; biased_group?: boolean }
export interface Simulation { simulated: boolean; reason?: string; brand?: string; groups: { persona: string; language: string; placebo_lift?: number; placebo_intent?: number; placebo_views?: number; biased?: boolean; error?: string }[]; scores: Record<string, Score> }
export interface Progress { generation: number; best: string; strength: number; ci: [number, number] | null; vs_gen0: number; verdict?: string; placebo?: number | null }
export interface EvolutionResult { generation: number; gen0: string; best: string; difference: number; retest_difference: number | null; noise_floor: number | null; verdict: string }
export interface Evolution {
  groups?: { persona: string; language: string; champion: string | null; history: { generation: number; scores?: Record<string, Score>; kept?: string[]; children?: string[]; stopped?: string }[];
    progress?: Progress[]; result?: EvolutionResult }[];
  skipped?: string; usd?: number;
}
export interface PlanAd { variant_id: string; template_id: string; image_path: string; headline_on_image: string; body: string; title: string; cta: string; sim_score: number }
export interface Plan { name: string; daily_cap_eur: number; daily_total_eur: number; ad_sets: { name: string; daily_budget_eur: number; audience: { persona: string; name: string; countries: string[]; age_min: number; age_max: number; gender: string }; ads: PlanAd[] }[]; notes: string[]; errors: string[] }
export interface Market { terms: string[]; category: string; advertisers_found: number; competitors: { page_id: string; why: string }[]; rejected: { page_id: string }[]; ads: number; research_countries: string[]; advertisers?: { page_id: string; page_name: string; ads: number }[] }
export interface Launch { ad_set: string; outcome: string; why: string }
export interface Published {
  mode: "sandbox" | "live"; account: string; objective: string; status: string; approved_by: string | null;
  objects: Record<string, string>; decisions: Launch[]; campaign_url: string | null;
}

/** A video ad the engine rendered (`whynot video`): one entry per file that still exists. */
export interface VideoAd {
  path: string; poster: string | null; seconds: number; hook: string; format: string; persona: string; tone: string | null;
  why: string; lufs: number | null; wordErrorRate: number | null; flags: string[];
}

/** A competitor's ad from the Ad Library, as the platform shows it (no snapshot URL: it can carry a token). */
export interface MarketAd { id: string; pageName: string; body: string; title: string; startDate: string | null; days: number | null; platforms: string[] }

export interface RunView {
  id: string;
  config: { app_ref: string; countries: string[]; daily_cap_eur: number; budget_usd: number; policy?: { level: string; daily_cap_eur: number } } | null;
  status: RunStatus;
  stages: StageView[];
  spentUsd: number;
  startedAt: string | null;
  app: App | null;
  brand: { palette: string[]; screenshots: string[] } | null;
  market: Market | null;
  strategy: Strategy | null;
  variants: Variant[];
  simulation: Simulation | null;
  evolution: Evolution | null;
  plan: Plan | null;
  launch: Launch[];
  published: Published | null;
  publishLog: string[];
  icon: string | null;
  log: RunEvent[];
  videos: VideoAd[];
  marketAds: MarketAd[];
  agency: AgencyView | null;  // a run started by the whole agency (`whynot agency`): its account, steps and days
}

/** The last lines the publish command printed (its own messages; tokens are redacted by the engine). */
function tail(dir: string, name: string, n = 6): string[] {
  const p = path.join(dir, name);
  if (!fs.existsSync(p)) return [];
  return fs.readFileSync(p, "utf8").trim().split("\n").slice(-n);
}

export function readRun(id: string, root: string = runsRoot(), now = Date.now()): RunView {
  const dir = resolveRun(id, root);
  const events = readEvents(dir);
  const stages = stageStates(events);
  const lastAt = events.length ? Date.parse(events[events.length - 1].ts) : null;
  const agency = readAgency(dir, now);
  // an agency run: the engine is alive while its command has not printed its last line
  const failed = agency && [agency.steps.connect, agency.steps.create, agency.steps.publish].some((s) => s?.status === "error");
  const status: RunStatus = agency?.running ? "running" : failed ? "failed" : runStatus(stages, lastAt, now);
  return {
    id,
    config: readJson(dir, "config.json"),
    status,
    stages,
    spentUsd: totalSpent(events),
    startedAt: events[0]?.ts ?? null,
    app: readJson(dir, "app.json"),
    brand: readJson(dir, "brand.json"),
    market: marketView(readJson<Json>(dir, "market.json")),
    strategy: readJson(dir, "strategy.json"),
    variants: readJson<Variant[]>(dir, "variants.json") ?? [],
    simulation: readJson(dir, "simulation.json"),
    evolution: readJson(dir, "evolution.json"),
    plan: readJson(dir, "plan.json"),
    launch: readJson<Launch[]>(dir, "launch.json") ?? [],
    published: readJson(dir, "publish.json"),
    publishLog: tail(dir, "publish.log"),
    icon: fs.existsSync(path.join(dir, "assets", "icon.png")) ? "assets/icon.png" : null,
    log: events.slice(-40),
    videos: readVideos(dir),
    marketAds: readMarketAds(dir, now),
    agency,
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Json = Record<string, any>; // engine output, checked field by field below

/** market.json reduced to the fields the platform shows (an allowlist: nothing else, e.g. a URL, reaches the browser). */
function marketView(m: Json | null): Market | null {
  if (!m) return null;
  const list = (x: unknown) => (Array.isArray(x) ? x : []);
  return {
    terms: list(m.terms).map(String), category: String(m.category ?? ""), advertisers_found: Number(m.advertisers_found ?? 0),
    competitors: list(m.competitors).map((c: Json) => ({ page_id: String(c.page_id), why: String(c.why ?? "") })),
    rejected: list(m.rejected).map((c: Json) => ({ page_id: String(c.page_id) })), ads: Number(m.ads ?? 0),
    research_countries: list(m.research_countries).map(String),
    advertisers: list(m.advertisers).map((a: Json) => ({ page_id: String(a.page_id), page_name: String(a.page_name ?? ""), ads: Number(a.ads ?? 0) })),
  };
}

/** A bare file name with the right extension: never a path out of its folder. */
const safeName = (n: unknown, ext: RegExp): n is string => typeof n === "string" && n === path.basename(n) && ext.test(n);

/**
 * Video ads from `videos/trends*.json` (each `whynot video` call writes its own file; `trends.json` is the
 * latest). Newest first, one entry per mp4, only files that are still on disk.
 */
export function readVideos(dir: string): VideoAd[] {
  const vdir = path.join(dir, "videos");
  if (!fs.existsSync(vdir)) return [];
  const seen = new Map<string, VideoAd>();
  for (const name of fs.readdirSync(vdir).filter((n) => /^trends(-\d+)?\.json$/.test(n))) {
    const doc = readJson<Json>(vdir, name);
    for (const v of (doc?.videos ?? []) as Json[]) {
      const file = v.file?.path;
      if (!safeName(file, /\.mp4$/i) || !fs.existsSync(path.join(vdir, file))) continue;
      const b = v.brief ?? {};
      const qa = v.file?.qa ?? {};
      seen.set(file, {
        path: `videos/${file}`,
        poster: safeName(v.poster, /\.(jpe?g|png)$/i) && fs.existsSync(path.join(vdir, v.poster)) ? `videos/${v.poster}` : null,
        seconds: Number(v.file?.seconds ?? 0), hook: String(b.hook ?? ""), format: String(b.format ?? ""),
        persona: String(b.persona ?? ""), tone: b.tone ? String(b.tone) : null, why: String(v.why ?? ""),
        lufs: typeof v.file?.loudness?.lufs === "number" ? v.file.loudness.lufs : null,
        wordErrorRate: typeof qa.word_error_rate === "number" ? qa.word_error_rate : null,
        flags: Array.isArray(qa.flags) ? qa.flags.map(String) : [],
      });
    }
  }
  const mtime = (p: string) => fs.statSync(path.join(dir, p)).mtimeMs;
  return [...seen.values()].sort((a, b) => mtime(b.path) - mtime(a.path));
}

/** Competitors' ads the scout read (`market_ads.jsonl`), longest-running first. */
export function readMarketAds(dir: string, now = Date.now()): MarketAd[] {
  const p = path.join(dir, "market_ads.jsonl");
  if (!fs.existsSync(p)) return [];
  return fs.readFileSync(p, "utf8").split("\n").filter(Boolean).flatMap((line): MarketAd[] => {
    try {
      const a = JSON.parse(line) as Json;
      const start = typeof a.start_date === "string" ? a.start_date : null;
      const end = typeof a.stop_date === "string" ? Date.parse(a.stop_date) : now;
      const t = start ? Date.parse(start) : NaN;
      const days = Number.isFinite(t) && Number.isFinite(end) ? Math.max(0, Math.round((end - t) / 86_400_000)) : null;
      return [{ id: String(a.id), pageName: String(a.page_name ?? ""), body: String(a.bodies?.[0] ?? ""),
        title: String(a.titles?.[0] ?? ""), startDate: start, days, platforms: Array.isArray(a.platforms) ? a.platforms.map(String) : [] }];
    } catch {
      return [];
    }
  }).sort((a, b) => (b.days ?? -1) - (a.days ?? -1));
}

/** Ad pictures from the finished runs, for the wall on the home page: the product, shown rather than told. */
export function showcase(root: string = runsRoot(), max = 18): { run: string; path: string }[] {
  const out: { run: string; path: string }[] = [];
  for (const r of listRuns(root)) {
    const dir = path.join(root, r.id);
    const plan = readJson<Plan>(dir, "plan.json");
    for (const s of plan?.ad_sets ?? []) for (const a of s.ads) if (a.image_path) out.push({ run: r.id, path: a.image_path });
    for (const v of readVideos(dir)) if (v.poster) out.push({ run: r.id, path: v.poster });
  }
  // alternate runs so one app doesn't fill a whole row
  return out.sort((a, b) => (a.path.length * 7 + a.run.length) % 5 - (b.path.length * 7 + b.run.length) % 5).slice(0, max);
}

export interface RunSummary { id: string; appName: string; status: RunStatus; startedAt: string | null; spentUsd: number; adSets: number; ads: number; videos: number; icon: string | null }

/** Runs under the root (and one level of sub-folders), newest first. */
export function listRuns(root: string = runsRoot(), now = Date.now()): RunSummary[] {
  if (!fs.existsSync(root)) return [];
  const ids: string[] = [];
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    if (fs.existsSync(path.join(root, entry.name, "config.json"))) ids.push(entry.name);
    else for (const sub of fs.readdirSync(path.join(root, entry.name), { withFileTypes: true }))
      if (sub.isDirectory() && fs.existsSync(path.join(root, entry.name, sub.name, "config.json"))) ids.push(`${entry.name}/${sub.name}`);
  }
  return ids.flatMap((id): RunSummary[] => {
    try {
      return [summarize(id, root, now)];
    } catch (e) {
      if (e instanceof RunPathError) return []; // e.g. a symlinked folder: skipped, never a broken page
      throw e;
    }
  }).sort((a, b) => (b.startedAt ?? "").localeCompare(a.startedAt ?? ""));
}

/** What the campaign list needs, without reading every file of every run. */
function summarize(id: string, root: string, now: number): RunSummary {
  const dir = resolveRun(id, root);
  const events = readEvents(dir);
  const stages = stageStates(events);
  const plan = readJson<Plan>(dir, "plan.json");
  const app = readJson<App>(dir, "app.json");
  const config = readJson<RunView["config"]>(dir, "config.json");
  const vdir = path.join(dir, "videos");
  return {
    id, appName: app?.name ?? config?.app_ref ?? id, status: runStatus(stages, events.length ? Date.parse(events[events.length - 1].ts) : null, now),
    startedAt: events[0]?.ts ?? null, spentUsd: totalSpent(events), adSets: plan?.ad_sets.length ?? 0,
    ads: plan?.ad_sets.reduce((n, s) => n + s.ads.length, 0) ?? 0,
    videos: fs.existsSync(vdir) ? fs.readdirSync(vdir).filter((n) => n.endsWith(".mp4")).length : 0,
    icon: fs.existsSync(path.join(dir, "assets", "icon.png")) ? "assets/icon.png" : null,
  };
}
