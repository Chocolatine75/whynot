/**
 * Publishing from the platform: readiness (which settings exist, never their values) and starting
 * `whynot publish`. The engine applies the autopilot rules; this layer only validates and spawns.
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { REPO_ROOT, resolveRun } from "./runs";

export type Mode = "sandbox" | "live";
export type Objective = "traffic" | "app_promotion";

const NEEDS: Record<Mode, string[]> = {
  sandbox: ["META_SANDBOX_AD_ACCOUNT_ID", "META_SANDBOX_TOKEN", "META_PAGE_ID"],
  live: ["META_AD_ACCOUNT_ID", "META_ACCESS_TOKEN", "META_PAGE_ID"],
};

/** Names of the settings that have a non-empty value in .env (values are never read out). */
export function configuredKeys(envFile = path.join(REPO_ROOT, ".env")): Set<string> {
  if (!fs.existsSync(envFile)) return new Set();
  const keys = new Set<string>();
  for (const line of fs.readFileSync(envFile, "utf8").split("\n")) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)$/);
    if (!m) continue;
    const value = m[2].split("#")[0].trim().replace(/^["']|["']$/g, "");
    if (value) keys.add(m[1]);
  }
  return keys;
}

export interface Readiness { mode: Mode; ready: boolean; missing: string[]; appInstalls: boolean }

export function readiness(keys: Set<string> = configuredKeys()): Readiness[] {
  return (["sandbox", "live"] as Mode[]).map((mode) => {
    const missing = NEEDS[mode].filter((k) => !keys.has(k));
    return { mode, ready: missing.length === 0, missing, appInstalls: keys.has("META_APP_ID") };
  });
}

export interface PublishRequest { id: string; mode: Mode; objective: Objective; approvedBy: string; activate: boolean }

export function validatePublish(input: unknown): { ok: true; value: PublishRequest } | { ok: false; error: string } {
  const o = (input ?? {}) as Record<string, unknown>;
  const id = String(o.id ?? "");
  const mode = o.mode === "live" ? "live" : o.mode === "sandbox" ? "sandbox" : null;
  const objective = o.objective === "app_promotion" ? "app_promotion" : o.objective === "traffic" ? "traffic" : null;
  const approvedBy = String(o.approvedBy ?? "").trim();
  if (!id) return { ok: false, error: "Missing campaign." };
  if (!mode) return { ok: false, error: "Choose sandbox or live." };
  if (!objective) return { ok: false, error: "Choose an objective." };
  // starts with a letter: a name like "--live" must never be read as an option by the engine's CLI
  if (!/^\p{L}[\p{L}\p{M}' .-]{1,59}$/u.test(approvedBy)) return { ok: false, error: "Type your name to approve (letters only)." };
  return { ok: true, value: { id, mode, objective, approvedBy, activate: o.activate === true && mode === "sandbox" } };
}

export function publishArgs(r: PublishRequest, runDir: string): string[] {
  return ["run", "whynot", "publish", runDir, `--objective=${r.objective}`, `--approve=${r.approvedBy}`,
    ...(r.mode === "live" ? ["--live"] : []), ...(r.activate ? ["--activate"] : [])];
}

export function startPublish(r: PublishRequest): void {
  const dir = resolveRun(r.id);
  const log = fs.openSync(path.join(dir, "publish.log"), "a");
  fs.writeSync(log, `\n--- ${new Date().toISOString()} ${r.mode} ${r.objective} approved by ${r.approvedBy}\n`);
  const child = spawn("uv", publishArgs(r, dir), { cwd: REPO_ROOT, detached: true, stdio: ["ignore", log, log], shell: false });
  child.unref();
}
