/**
 * The owner's Meta account on the platform: connect once, then the agency runs on it.
 *
 * - `whynot connect --token-stdin --json`: the login token goes to the engine on stdin (never in argv, a file
 *   the site writes, or a log). The engine exchanges it for a 60-day token and saves the connection in
 *   `data/private/connections/act_<id>.json` (mode 600). This module reads those files but never returns the token.
 * - `whynot agency ... --connection <file> --run-dir <dir>`: the whole agency on that account, in the background.
 * - `whynot agency --resume <dir> [--approve NAME]`, `whynot schedule <dir> --at HH:MM`, `whynot stop <dir>
 *   --connection <file>`: the owner's buttons.
 * Every engine call is spawned without a shell (argument array); every value is checked here first. The engine
 * enforces the cap, the autonomy level and the approvals again: this layer can never make it spend more.
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { newRunId } from "./start";
import { REPO_ROOT, resolveRun, runsRoot } from "./runs";

export function connectionsDir(): string {
  return path.resolve(process.env.WHYNOT_CONNECTIONS_DIR ?? path.join(REPO_ROOT, "data", "private", "connections"));
}

/** A saved connection as the browser may see it: everything but the token. */
export interface Connection {
  act: string; accountId: string; accountName: string; currency: string; pageId: string | null; pageName: string | null;
  appId: string | null; userName: string; sandbox: boolean; warnings: string[]; connectedAt: string | null;
  expiresAt: string | null; daysLeft: number | null; canPublish: boolean;
}

const ACCOUNT_ID = /^\d{3,20}$/;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Json = Record<string, any>;

function toConnection(d: Json, now: number): Connection | null {
  const id = String(d.account_id ?? "");
  if (!ACCOUNT_ID.test(id)) return null;
  const granted = Array.isArray(d.granted) ? d.granted.map(String) : [];
  const expiresAt = typeof d.expires_at === "string" ? d.expires_at : null;
  const t = expiresAt ? Date.parse(expiresAt) : NaN;
  return {
    act: `act_${id}`, accountId: id, accountName: String(d.account_name ?? ""), currency: String(d.currency ?? ""),
    pageId: d.page_id ? String(d.page_id) : null, pageName: d.page_name ? String(d.page_name) : null,
    appId: d.app_id ? String(d.app_id) : null, userName: String(d.user_name ?? ""), sandbox: d.sandbox === true,
    warnings: Array.isArray(d.warnings) ? d.warnings.map(String) : [],
    connectedAt: typeof d.connected_at === "string" ? d.connected_at : null, expiresAt,
    daysLeft: Number.isFinite(t) ? Math.floor((t - now) / 86_400_000) : null,
    canPublish: granted.includes("ads_management") && Boolean(d.page_id),
  };
}

/** Saved connections, newest first. Unreadable files are skipped. */
export function listConnections(dir: string = connectionsDir(), now = Date.now()): Connection[] {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter((n) => /^act_\d+\.json$/.test(n)).flatMap((n) => {
    try {
      const c = toConnection(JSON.parse(fs.readFileSync(path.join(dir, n), "utf8")), now);
      return c ? [c] : [];
    } catch {
      return [];
    }
  }).sort((a, b) => (b.connectedAt ?? "").localeCompare(a.connectedAt ?? ""));
}

/** The private file of a connection, from its account id only (never a path the client sends). */
export function connectionFile(accountId: string, dir: string = connectionsDir()): string | null {
  if (!ACCOUNT_ID.test(accountId)) return null;
  const file = path.join(dir, `act_${accountId}.json`);
  return fs.existsSync(file) ? file : null;
}

/** whynot's developer app id (public: Facebook Login needs it in the page). Never another value of .env. */
export function loginAppId(envFile = path.join(REPO_ROOT, ".env")): string | null {
  const fromEnv = process.env.WHYNOT_META_APP_ID;
  if (fromEnv && /^\d{5,20}$/.test(fromEnv)) return fromEnv;
  if (!fs.existsSync(envFile)) return null;
  const m = fs.readFileSync(envFile, "utf8").match(/^\s*WHYNOT_META_APP_ID\s*=\s*["']?(\d{5,20})["']?\s*(#.*)?$/m);
  return m ? m[1] : null;
}

// ---------- connect ----------

export interface ConnectRequest { token: string; account?: string; page?: string; appId?: string }

const TOKEN = /^[A-Za-z0-9_\-.|]{20,2000}$/;
const META_ID = /^\d{3,25}$/;

export function validateConnect(input: unknown): { ok: true; value: ConnectRequest } | { ok: false; error: string } {
  const o = (input ?? {}) as Record<string, unknown>;
  const token = String(o.token ?? "").trim();
  if (!TOKEN.test(token)) return { ok: false, error: "That doesn't look like a Meta login token." };
  const value: ConnectRequest = { token };
  for (const key of ["account", "page", "appId"] as const) {
    const v = String(o[key] ?? "").trim().replace(/^act_/, "");
    if (!v) continue;
    if (!META_ID.test(v)) return { ok: false, error: `The ${key === "appId" ? "app" : key} id is digits only.` };
    value[key] = v;
  }
  return { ok: true, value };
}

export function connectArgs(r: ConnectRequest): string[] {
  return ["run", "whynot", "connect", "--token-stdin", "--json",
    ...(r.account ? [`--account=${r.account}`] : []), ...(r.page ? [`--page=${r.page}`] : []),
    ...(r.appId ? [`--app-id=${r.appId}`] : [])];
}

export type ConnectResult = { ok: true; connection: Connection } | { ok: false; error: string };

/** Run `whynot connect`, the token on stdin; returns the connection without its token. */
export function runConnect(r: ConnectRequest, { command = "uv", timeoutMs = 60_000, dir = connectionsDir() } = {}): Promise<ConnectResult> {
  return new Promise((resolve) => {
    const child = spawn(command, connectArgs(r), { cwd: REPO_ROOT, shell: false });
    let out = "";
    let err = "";
    child.stdout.on("data", (d) => { out += d; });
    child.stderr.on("data", (d) => { err += d; });
    const timer = setTimeout(() => child.kill("SIGTERM"), timeoutMs);
    let settled = false;
    const finish = (res: ConnectResult) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(res);
    };
    child.on("error", (e) => finish({ ok: false, error: `Could not start the engine: ${e.message}` }));
    child.on("close", () => {
      const line = out.trim().split("\n").filter((l) => l.startsWith("{")).at(-1);
      let d: Json | null = null;
      try { d = line ? JSON.parse(line) : null; } catch { d = null; }
      if (!d) return finish({ ok: false, error: scrub(err.trim().split("\n").at(-1) ?? "", r.token) || "Meta did not answer." });
      if (!d.ok) return finish({ ok: false, error: scrub(String(d.error ?? "Connection refused."), r.token) });
      const saved = connectionFile(String(d.account_id ?? ""), dir);
      const c = saved ? toConnection(JSON.parse(fs.readFileSync(saved, "utf8")), Date.now()) : toConnection(d, Date.now());
      finish(c ? { ok: true, connection: c } : { ok: false, error: "The engine answered without an ad account." });
    });
    child.stdin.on("error", () => { /* the engine exited before reading: reported on close */ });
    child.stdin.end(r.token + "\n");
  });
}

/** Never echo the token back, even inside an error message. */
export function scrub(text: string, token: string): string {
  return (token ? text.split(token).join("[token]") : text).replace(/(access_token=)[^&\s"']+/g, "$1[token]");
}

// ---------- the agency ----------

export const LEVELS = ["dry_run", "propose", "autopilot"] as const;
export type Level = (typeof LEVELS)[number];

export interface AgencyRequest {
  app: string; countries: string[]; dailyCapEur: number; budgetUsd: number;
  account: string | null;  // a saved connection's account id; null = simulated account (results invented, labelled)
  level: Level; paused: boolean; landingUrl: string | null;
}

const APP_REF = /^(https:\/\/apps\.apple\.com\/[^\s]{4,300}|\d{6,12})$/;
const COUNTRY = /^[A-Z]{2}$/;

export function validateAgency(input: unknown, connections: Connection[] = listConnections()):
  { ok: true; value: AgencyRequest } | { ok: false; error: string } {
  const o = (input ?? {}) as Record<string, unknown>;
  const app = String(o.app ?? "").trim();
  if (!APP_REF.test(app)) return { ok: false, error: "Paste an App Store link (https://apps.apple.com/...) or the app's id." };
  const raw = Array.isArray(o.countries) ? o.countries : String(o.countries ?? "").split(/[\s,]+/);
  const countries = [...new Set(raw.map((c) => String(c).trim().toUpperCase()).filter(Boolean))];
  if (!countries.length || countries.length > 10 || !countries.every((c) => COUNTRY.test(c)))
    return { ok: false, error: "Countries are 2-letter codes, e.g. US or FR GB (up to 10)." };
  const cap = Number(o.dailyCapEur);
  if (!Number.isFinite(cap) || cap < 5 || cap > 10_000) return { ok: false, error: "The daily budget must be between €5 and €10,000." };
  const budget = o.budgetUsd === undefined || o.budgetUsd === "" ? 8 : Number(o.budgetUsd);
  if (!Number.isFinite(budget) || budget <= 0 || budget > 20) return { ok: false, error: "The AI budget must be between $0 and $20." };
  const level = LEVELS.find((l) => l === o.level) ?? "dry_run";
  let account: string | null = null;
  if (o.account) {
    const c = connections.find((x) => x.accountId === String(o.account).replace(/^act_/, ""));
    if (!c) return { ok: false, error: "Connect this Meta ad account first." };
    if (!c.canPublish) return { ok: false, error: "This Meta login cannot publish ads (needs ads_management and a Page)." };
    if (c.daysLeft !== null && c.daysLeft < 0) return { ok: false, error: "Your Meta login has expired: connect again." };
    account = c.accountId;
  }
  const landing = String(o.landingUrl ?? "").trim();
  if (landing && !/^https:\/\/[^\s]{4,300}$/.test(landing)) return { ok: false, error: "The website must start with https://." };
  return { ok: true, value: { app, countries, dailyCapEur: cap, budgetUsd: budget, account, level,
    paused: o.paused !== false, landingUrl: landing || null } };
}

export function agencyArgs(r: AgencyRequest, runDir: string, connection: string | null): string[] {
  return ["run", "whynot", "agency", r.app, "--countries", ...r.countries, `--daily-cap=${r.dailyCapEur}`,
    `--budget-usd=${r.budgetUsd}`, ...(connection ? [`--connection=${connection}`] : ["--sim"]),
    `--level=${r.level}`, ...(r.paused ? ["--paused"] : []), ...(r.landingUrl ? [`--landing-url=${r.landingUrl}`] : []),
    `--run-dir=${runDir}`, "--json"];
}

function spawnLogged(args: string[], dir: string, header: string, command = "uv"): void {
  fs.mkdirSync(path.join(dir, "agency"), { recursive: true });
  const log = fs.openSync(path.join(dir, "agency", "site.log"), "a");
  fs.writeSync(log, `\n--- ${new Date().toISOString()} ${header}\n`);
  const child = spawn(command, args, { cwd: REPO_ROOT, detached: true, stdio: ["ignore", log, log], shell: false });
  child.on("error", (e) => fs.appendFileSync(path.join(dir, "agency", "site.log"), `✗ could not start the engine: ${e.message}\n`));
  child.unref();
}

/** Start the whole agency in the background; returns the run id (its page opens at once). */
export function startAgency(r: AgencyRequest, { command = "uv", root = runsRoot() } = {}): string {
  const id = newRunId(r.app);
  const dir = path.join(root, id);
  fs.mkdirSync(dir, { recursive: true });
  // the engine writes config.json when `create` starts; a placeholder lets the page open now
  fs.writeFileSync(path.join(dir, "config.json"), JSON.stringify({ app_ref: r.app, countries: r.countries, daily_cap_eur: r.dailyCapEur, budget_usd: r.budgetUsd }));
  const conn = r.account ? connectionFile(r.account) : null;
  spawnLogged(agencyArgs(r, dir, conn), dir, `start ${r.account ? `act_${r.account}` : "simulated account"} ${r.level}${r.paused ? " paused" : ""}`, command);
  return id;
}

// the owner's name: starts with a letter, so a name like "--live" is never read as an option by the engine
const NAME = /^\p{L}[\p{L}\p{M}' .-]{1,59}$/u;

export interface ResumeRequest { id: string; approvedBy: string | null }

export function validateResume(input: unknown): { ok: true; value: ResumeRequest } | { ok: false; error: string } {
  const o = (input ?? {}) as Record<string, unknown>;
  const id = String(o.id ?? "");
  if (!id) return { ok: false, error: "Missing campaign." };
  const name = String(o.approvedBy ?? "").trim();
  if (name && !NAME.test(name)) return { ok: false, error: "Type your name to approve (letters only)." };
  return { ok: true, value: { id, approvedBy: name || null } };
}

export function resumeArgs(r: ResumeRequest, runDir: string): string[] {
  return ["run", "whynot", "agency", `--resume=${runDir}`, ...(r.approvedBy ? [`--approve=${r.approvedBy}`] : []), "--json"];
}

/** Today's day (or a step waiting for approval), in the background. */
export function resumeAgency(r: ResumeRequest, { command = "uv", root = runsRoot() } = {}): void {
  const dir = resolveRun(r.id, root);
  if (!fs.existsSync(path.join(dir, "agency", "state.json"))) throw new Error("not an agency run");
  spawnLogged(resumeArgs(r, dir), dir, r.approvedBy ? `resume, approved by ${r.approvedBy}` : "resume", command);
}

// ---------- engine calls the page waits for (seconds): schedule, stop ----------

function runAndWait(command: string, args: string[], timeoutMs: number): Promise<{ code: number | null; out: string; err: string }> {
  return new Promise((resolve) => {
    const child = spawn(command, args, { cwd: REPO_ROOT, shell: false, stdio: ["ignore", "pipe", "pipe"] });
    let out = "";
    let err = "";
    child.stdout.on("data", (d) => { out += d; });
    child.stderr.on("data", (d) => { err += d; });
    const timer = setTimeout(() => child.kill("SIGTERM"), timeoutMs);
    let settled = false;
    const finish = (code: number | null, extra = "") => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({ code, out, err: err + extra });
    };
    child.on("error", (e) => finish(null, `could not start the engine: ${e.message}`));
    child.on("close", (code) => finish(code));
  });
}

export interface ScheduleRequest { id: string; at: string | null }  // at null = remove

export function validateSchedule(input: unknown): { ok: true; value: ScheduleRequest } | { ok: false; error: string } {
  const o = (input ?? {}) as Record<string, unknown>;
  const id = String(o.id ?? "");
  if (!id) return { ok: false, error: "Missing campaign." };
  if (o.remove === true) return { ok: true, value: { id, at: null } };
  const at = String(o.at ?? "").trim();
  if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(at)) return { ok: false, error: "Pick a time, HH:MM." };
  return { ok: true, value: { id, at } };
}

export function scheduleArgs(r: ScheduleRequest, runDir: string): string[] {
  return ["run", "whynot", "schedule", runDir, ...(r.at ? [`--at=${r.at}`] : ["--remove"]), "--json"];
}

export async function runSchedule(r: ScheduleRequest, { command = "uv", root = runsRoot(), timeoutMs = 60_000 } = {}):
  Promise<{ ok: boolean; error?: string }> {
  const dir = resolveRun(r.id, root);
  if (!fs.existsSync(path.join(dir, "agency", "state.json"))) return { ok: false, error: "Not an agency campaign." };
  const res = await runAndWait(command, scheduleArgs(r, dir), timeoutMs);
  return res.code === 0 ? { ok: true } : { ok: false, error: res.err.trim().split("\n").at(-1)?.replace(/^✗\s*/, "") || "The schedule failed." };
}

export interface AgencyStopRequest { id: string; by: string }

export function validateAgencyStop(input: unknown): { ok: true; value: AgencyStopRequest } | { ok: false; error: string } {
  const o = (input ?? {}) as Record<string, unknown>;
  const id = String(o.id ?? "");
  const by = String(o.by ?? "").trim();
  if (!id) return { ok: false, error: "Missing campaign." };
  if (!NAME.test(by)) return { ok: false, error: "Type your name (letters only)." };
  return { ok: true, value: { id, by } };
}

/** The kill switch on the account the agency used. Returns what the engine printed (no token: it never prints it). */
export async function runAgencyStop(r: AgencyStopRequest, { command = "uv", root = runsRoot(), timeoutMs = 60_000 } = {}):
  Promise<{ ok: boolean; lines: string[] }> {
  const dir = resolveRun(r.id, root);
  const account = readAgency(dir)?.account?.accountId;
  const conn = account ? connectionFile(account) : null;
  if (!conn) return { ok: false, lines: ["✗ this campaign has no Meta connection: nothing was published on Meta"] };
  const res = await runAndWait(command, ["run", "whynot", "stop", dir, `--by=${r.by}`, `--connection=${conn}`], timeoutMs);
  const text = `${res.out}\n${res.err}`;
  fs.appendFileSync(path.join(dir, "stop.log"), `\n--- ${new Date().toISOString()} agency stop by ${r.by}\n${text}\n`);
  return { ok: res.code === 0, lines: text.split("\n").map((l) => l.trimEnd()).filter(Boolean) };
}

// ---------- what the run page shows ----------

export interface AgencyStep { status: string; at: string | null; usd: number; outputs: Json; error: string | null }
export interface AgencyView {
  account: Connection | null;  // null: the simulated account
  simulated: boolean; level: string; paused: boolean; dailyCapEur: number; objective: string | null; website: string | null;
  steps: Record<"connect" | "create" | "publish", AgencyStep | null>;
  days: (AgencyStep & { day: string })[];
  waiting: boolean; firstLiveApprovedBy: string | null; schedule: { at: string; how: string; installed: boolean } | null;
  running: boolean;  // the engine wrote to the run in the last minutes
  log: string[];
}

function step(d: Json | undefined): AgencyStep | null {
  if (!d || typeof d !== "object") return null;
  const outputs: Json = d.outputs && typeof d.outputs === "object" ? { ...d.outputs } : {};
  delete outputs.token;  // never in the state; dropped again here in case
  return { status: String(d.status ?? ""), at: typeof d.at === "string" ? d.at : null, usd: Number(d.usd ?? 0),
    outputs, error: d.error ? String(d.error) : null };
}

/** `agency/state.json` reduced to what the page shows; null for a run started with `whynot create` only. */
export function readAgency(dir: string, now = Date.now()): AgencyView | null {
  const p = path.join(dir, "agency", "state.json");
  const started = fs.existsSync(path.join(dir, "agency", "site.log"));  // the site started it; the engine may not have saved yet
  if (!fs.existsSync(p) && !started) return null;
  let s: Json = { steps: {}, days: {}, config: {} };
  if (fs.existsSync(p)) {
    try { s = JSON.parse(fs.readFileSync(p, "utf8")); } catch { /* being written: show the empty state */ }
  }
  const cfg: Json = s.config ?? {};
  const steps = s.steps ?? {};
  const days = Object.entries((s.days ?? {}) as Json).map(([day, d]) => ({ day, ...step(d as Json)! })).sort((a, b) => b.day.localeCompare(a.day));
  const all = [steps.connect, steps.create, steps.publish, ...Object.values(s.days ?? {})].filter(Boolean) as Json[];
  const logFile = path.join(dir, "agency", "site.log");
  const mtime = (f: string) => (fs.existsSync(f) ? fs.statSync(f).mtimeMs : 0);
  const touched = Math.max(mtime(p), mtime(path.join(dir, "events.jsonl")), mtime(logFile));
  const logLines = fs.existsSync(logFile) ? fs.readFileSync(logFile, "utf8").trim().split("\n") : [];
  const lastStart = logLines.map((l) => l.startsWith("--- ")).lastIndexOf(true);
  const finished = lastStart >= 0 && logLines.slice(lastStart + 1).some((l) => l.startsWith("{\"ok\"") || l.startsWith("✗"));
  return {
    account: s.account ? toConnection(s.account, now) : null,
    simulated: cfg.simulated_account === true, level: String(cfg.level ?? "dry_run"), paused: cfg.paused_only === true,
    dailyCapEur: Number(cfg.daily_cap_eur ?? 0), objective: s.objective ? String(s.objective) : null,
    website: typeof s.website === "string" ? s.website : null,
    steps: { connect: step(steps.connect), create: step(steps.create), publish: step(steps.publish) },
    days, waiting: all.some((d) => d.status === "waiting"),
    firstLiveApprovedBy: s.first_live_approved_by ? String(s.first_live_approved_by) : null,
    schedule: s.schedule ? { at: String(s.schedule.at ?? ""), how: String(s.schedule.how ?? ""), installed: s.schedule.installed === true } : null,
    running: lastStart >= 0 && !finished && now - touched < 10 * 60_000,
    log: logLines.slice(lastStart >= 0 ? lastStart + 1 : 0).filter((l) => !l.startsWith("{")).slice(-6).map((l) => l.replace(/(access_token=)[^&\s"']+/g, "$1[token]")),
  };
}
