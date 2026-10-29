/**
 * Read `whynot create` run folders for the client platform.
 *
 * A run folder is written by the Python engine (src/whynot/agency/create.py): JSON per stage, an
 * append-only events.jsonl, ads/*.png. This module only reads it. Every path is resolved inside the
 * runs root; anything that escapes it is refused.
 */
import fs from "node:fs";
import path from "node:path";

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

const SERVABLE = new Map([[".png", "image/png"], [".jpg", "image/jpeg"], [".jpeg", "image/jpeg"], [".md", "text/markdown; charset=utf-8"]]);

/** A file inside a run that the browser may load (ad images, screenshots, the report). */
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
export interface Simulation { simulated: boolean; reason?: string; brand?: string; groups: { persona: string; language: string; placebo_lift?: number; placebo_views?: number; biased?: boolean; error?: string }[]; scores: Record<string, Score> }
export interface Evolution { groups?: { persona: string; language: string; champion: string | null; history: { generation: number; scores?: Record<string, Score>; kept?: string[]; children?: string[]; stopped?: string }[] }[]; skipped?: string; usd?: number }
export interface PlanAd { variant_id: string; template_id: string; image_path: string; headline_on_image: string; body: string; title: string; cta: string; sim_score: number }
export interface Plan { name: string; daily_cap_eur: number; daily_total_eur: number; ad_sets: { name: string; daily_budget_eur: number; audience: { persona: string; name: string; countries: string[]; age_min: number; age_max: number; gender: string }; ads: PlanAd[] }[]; notes: string[]; errors: string[] }
export interface Market { terms: string[]; category: string; advertisers_found: number; competitors: { page_id: string; why: string }[]; rejected: { page_id: string }[]; ads: number; research_countries: string[]; advertisers?: { page_id: string; page_name: string; ads: number }[] }
export interface Launch { ad_set: string; outcome: string; why: string }

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
}

export function readRun(id: string, root: string = runsRoot(), now = Date.now()): RunView {
  const dir = resolveRun(id, root);
  const events = readEvents(dir);
  const stages = stageStates(events);
  const lastAt = events.length ? Date.parse(events[events.length - 1].ts) : null;
  return {
    id,
    config: readJson(dir, "config.json"),
    status: runStatus(stages, lastAt, now),
    stages,
    spentUsd: totalSpent(events),
    startedAt: events[0]?.ts ?? null,
    app: readJson(dir, "app.json"),
    brand: readJson(dir, "brand.json"),
    market: readJson(dir, "market.json"),
    strategy: readJson(dir, "strategy.json"),
    variants: readJson<Variant[]>(dir, "variants.json") ?? [],
    simulation: readJson(dir, "simulation.json"),
    evolution: readJson(dir, "evolution.json"),
    plan: readJson(dir, "plan.json"),
    launch: readJson<Launch[]>(dir, "launch.json") ?? [],
  };
}

export interface RunSummary { id: string; appName: string; status: RunStatus; startedAt: string | null; spentUsd: number; adSets: number; ads: number }

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
  return ids.map((id) => {
    const r = readRun(id, root, now);
    return { id, appName: r.app?.name ?? r.config?.app_ref ?? id, status: r.status, startedAt: r.startedAt, spentUsd: r.spentUsd,
      adSets: r.plan?.ad_sets.length ?? 0, ads: r.plan?.ad_sets.reduce((n, s) => n + s.ads.length, 0) ?? 0 };
  }).sort((a, b) => (b.startedAt ?? "").localeCompare(a.startedAt ?? ""));
}
