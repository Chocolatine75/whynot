/**
 * Start `whynot create` from the platform. Inputs are validated here; the engine is spawned without a
 * shell (argument array), so nothing the client types can be interpreted as a command.
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { REPO_ROOT, runsRoot } from "./runs";

export interface NewCampaign { app: string; countries: string[]; dailyCapEur: number; budgetUsd: number }

const APP_REF = /^(https?:\/\/[^\s]{4,300}|\d{6,12})$/;
const COUNTRY = /^[A-Z]{2}$/;

export function validateCampaign(input: unknown): { ok: true; value: NewCampaign } | { ok: false; error: string } {
  const o = (input ?? {}) as Record<string, unknown>;
  const app = String(o.app ?? "").trim();
  if (!APP_REF.test(app)) return { ok: false, error: "Paste an App Store link (https://apps.apple.com/...) or the app's id." };
  const raw = Array.isArray(o.countries) ? o.countries : String(o.countries ?? "").split(/[\s,]+/);
  const countries = [...new Set(raw.map((c) => String(c).trim().toUpperCase()).filter(Boolean))];
  if (!countries.length || countries.length > 10 || !countries.every((c) => COUNTRY.test(c)))
    return { ok: false, error: "Countries are 2-letter codes, e.g. US or FR GB (up to 10)." };
  const cap = Number(o.dailyCapEur);
  if (!Number.isFinite(cap) || cap < 5 || cap > 10_000) return { ok: false, error: "The daily budget must be between €5 and €10,000." };
  const budget = o.budgetUsd === undefined || o.budgetUsd === "" ? 3 : Number(o.budgetUsd);
  if (!Number.isFinite(budget) || budget <= 0 || budget > 20) return { ok: false, error: "The AI budget must be between $0 and $20." };
  return { ok: true, value: { app, countries, dailyCapEur: cap, budgetUsd: budget } };
}

export function newRunId(app: string, now = new Date()): string {
  const stamp = now.toISOString().replace(/[-:]/g, "").replace("T", "-").slice(0, 15);
  const slug = (app.split("/").filter(Boolean).pop() ?? "app").toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 40);
  return `web/${stamp}-${slug || "app"}`;
}

export function engineArgs(c: NewCampaign, runDir: string): string[] {
  return ["run", "whynot", "create", c.app, "--countries", ...c.countries, "--daily-cap", String(c.dailyCapEur),
    "--budget-usd", String(c.budgetUsd), "--resume", runDir];
}

/** Spawn the engine in the background; returns the run id. Output goes to run.log in the run folder. */
export function startCampaign(c: NewCampaign): string {
  const id = newRunId(c.app);
  const dir = path.join(runsRoot(), id);
  fs.mkdirSync(dir, { recursive: true });
  const log = fs.openSync(path.join(dir, "run.log"), "a");
  const child = spawn("uv", engineArgs(c, dir), { cwd: REPO_ROOT, detached: true, stdio: ["ignore", log, log], shell: false });
  child.unref();
  // the engine writes config.json first; write a placeholder so the page can open immediately
  if (!fs.existsSync(path.join(dir, "config.json")))
    fs.writeFileSync(path.join(dir, "config.json"), JSON.stringify({ app_ref: c.app, countries: c.countries, daily_cap_eur: c.dailyCapEur, budget_usd: c.budgetUsd }));
  return id;
}
