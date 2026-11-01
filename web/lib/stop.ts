/**
 * The kill switch from the platform: runs `whynot stop <run> --by=<name> [--live]` and waits for it
 * (it takes seconds). The engine pauses everything the run created on Meta and logs it; this layer only
 * validates the request, starts the engine without a shell, and reports what it printed.
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { configuredKeys, type Mode } from "./publish";
import { REPO_ROOT, resolveRun } from "./runs";

export interface StopRequest { id: string; mode: Mode; by: string }

const NEEDS: Record<Mode, string[]> = {
  sandbox: ["META_SANDBOX_AD_ACCOUNT_ID", "META_SANDBOX_TOKEN"],
  live: ["META_AD_ACCOUNT_ID", "META_ACCESS_TOKEN"],
};

export function missingForStop(mode: Mode, keys: Set<string> = configuredKeys()): string[] {
  return NEEDS[mode].filter((k) => !keys.has(k));
}

export function validateStop(input: unknown): { ok: true; value: StopRequest } | { ok: false; error: string } {
  const o = (input ?? {}) as Record<string, unknown>;
  const id = String(o.id ?? "");
  const mode = o.mode === "live" ? "live" : o.mode === "sandbox" ? "sandbox" : null;
  const by = String(o.by ?? "").trim();
  if (!id) return { ok: false, error: "Missing campaign." };
  if (!mode) return { ok: false, error: "Choose sandbox or live." };
  // starts with a letter: a name like "--live" must never be read as an option by the engine's CLI
  if (!/^\p{L}[\p{L}\p{M}' .-]{1,59}$/u.test(by)) return { ok: false, error: "Type your name (letters only)." };
  return { ok: true, value: { id, mode, by } };
}

export function stopArgs(r: StopRequest, runDir: string): string[] {
  return ["run", "whynot", "stop", runDir, `--by=${r.by}`, ...(r.mode === "live" ? ["--live"] : [])];
}

export interface StopResult { ok: boolean; lines: string[] }

/** Run the kill switch and wait for it (at most `timeoutMs`); the output also goes to `<run>/stop.log`. */
export function runStop(r: StopRequest, { timeoutMs = 60_000, command = "uv" } = {}): Promise<StopResult> {
  const dir = resolveRun(r.id);
  return new Promise((resolve) => {
    const child = spawn(command, stopArgs(r, dir), { cwd: REPO_ROOT, shell: false });
    let out = "";
    child.stdout.on("data", (d) => { out += d; });
    child.stderr.on("data", (d) => { out += d; });
    const timer = setTimeout(() => child.kill("SIGTERM"), timeoutMs);
    let settled = false;
    const finish = (ok: boolean, extra?: string) => {
      if (settled) return;  // a failed start can emit both "error" and "close"
      settled = true;
      clearTimeout(timer);
      const text = out + (extra ? `\n${extra}` : "");
      fs.appendFileSync(path.join(dir, "stop.log"), `\n--- ${new Date().toISOString()} ${r.mode} by ${r.by}\n${text}\n`);
      resolve({ ok, lines: text.split("\n").map((l) => l.trimEnd()).filter(Boolean) });
    };
    child.on("error", (e) => finish(false, `✗ could not start the engine: ${e.message}`));
    child.on("close", (code) => finish(code === 0));
  });
}
