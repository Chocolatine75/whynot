import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  agencyArgs, connectArgs, connectionFile, listConnections, loginAppId, readAgency, resumeAgency, resumeArgs, runAgencyStop,
  runConnect, runSchedule, scheduleArgs, scrub, startAgency, validateAgency, validateAgencyStop, validateConnect,
  validateResume, validateSchedule, type Connection,
} from "@/lib/meta";
import { RunPathError, readRun } from "@/lib/runs";

const TOKEN = "EAAtestTOKEN1234567890abcdefXYZ";
const APP = "https://apps.apple.com/us/app/vietbuddy/id6796837982";

let root: string;
const saved = { runs: process.env.WHYNOT_RUNS_DIR, conns: process.env.WHYNOT_CONNECTIONS_DIR, app: process.env.WHYNOT_META_APP_ID };

beforeEach(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), "meta-"));
  process.env.WHYNOT_RUNS_DIR = path.join(root, "runs");
  process.env.WHYNOT_CONNECTIONS_DIR = path.join(root, "connections");
  fs.mkdirSync(process.env.WHYNOT_RUNS_DIR, { recursive: true });
  delete process.env.WHYNOT_META_APP_ID;
});
afterEach(() => {
  for (const [k, v] of [["WHYNOT_RUNS_DIR", saved.runs], ["WHYNOT_CONNECTIONS_DIR", saved.conns], ["WHYNOT_META_APP_ID", saved.app]] as const)
    if (v === undefined) delete process.env[k]; else process.env[k] = v;
});

function saveConnection(over: Record<string, unknown> = {}): string {
  const dir = process.env.WHYNOT_CONNECTIONS_DIR!;
  fs.mkdirSync(dir, { recursive: true });
  const d = { token: TOKEN, account_id: "2579757785851312", account_name: "Owner", currency: "EUR", page_id: "135", page_name: "Whynot test",
    app_id: null, user_name: "Owner", granted: ["ads_management", "ads_read"], sandbox: false, warnings: [],
    connected_at: "2026-11-02T10:00:00+00:00", expires_at: new Date(Date.now() + 40 * 86_400_000).toISOString(), ...over };
  const file = path.join(dir, `act_${d.account_id}.json`);
  fs.writeFileSync(file, JSON.stringify(d));
  return file;
}

/** A stand-in engine: records its arguments and stdin, prints what the test asks. */
function fakeEngine(script: string): string {
  const file = path.join(root, "fake-uv.sh");
  fs.writeFileSync(file, `#!/bin/sh\nprintf '%s\\n' "$@" > "${root}/args.txt"\ncat > "${root}/stdin.txt"\n${script}\n`);
  fs.chmodSync(file, 0o755);
  return file;
}

/** The background engine writes its arguments when it starts: wait for that file (a busy machine can be slow). */
async function argsWritten(): Promise<string[]> {
  const file = path.join(root, "args.txt");
  for (let i = 0; i < 100 && !fs.existsSync(file); i++) await new Promise((r) => setTimeout(r, 50));
  await new Promise((r) => setTimeout(r, 50));
  return fs.readFileSync(file, "utf8").split("\n");
}

function agencyRun(state: Record<string, unknown>, id = "web/x"): string {
  const dir = path.join(process.env.WHYNOT_RUNS_DIR!, id);
  fs.mkdirSync(path.join(dir, "agency"), { recursive: true });
  fs.writeFileSync(path.join(dir, "config.json"), JSON.stringify({ app_ref: APP, countries: ["US"], daily_cap_eur: 20, budget_usd: 8 }));
  fs.writeFileSync(path.join(dir, "agency", "state.json"), JSON.stringify(state));
  return dir;
}

describe("saved connections", () => {
  it("are listed without their token", () => {
    saveConnection();
    const list = listConnections();
    expect(list).toHaveLength(1);
    expect(list[0]).toMatchObject({ act: "act_2579757785851312", pageName: "Whynot test", canPublish: true });
    expect(list[0].daysLeft).toBeGreaterThanOrEqual(39);
    expect(JSON.stringify(list)).not.toContain(TOKEN);
  });

  it("cannot publish without ads_management or a Page; junk files are skipped", () => {
    saveConnection({ granted: ["ads_read"] });
    saveConnection({ account_id: "777", page_id: null });
    fs.writeFileSync(path.join(process.env.WHYNOT_CONNECTIONS_DIR!, "act_9.json"), "{not json");
    expect(listConnections().map((c) => c.canPublish)).toEqual([false, false]);
  });

  it("a connection file is found from its account id only, never from a path", () => {
    const file = saveConnection();
    expect(connectionFile("2579757785851312")).toBe(file);
    expect(connectionFile("../../etc/passwd")).toBeNull();
    expect(connectionFile("123")).toBeNull();
  });

  it("only whynot's app id is read from .env", () => {
    const env = path.join(root, ".env");
    fs.writeFileSync(env, "WHYNOT_META_APP_SECRET=shh\nWHYNOT_META_APP_ID=1689171966196247 # dev app\n");
    expect(loginAppId(env)).toBe("1689171966196247");
    fs.writeFileSync(env, "WHYNOT_META_APP_ID=abc\n");
    expect(loginAppId(env)).toBeNull();
  });
});

describe("connect", () => {
  it("validates the token and ids, and never puts the token in the arguments", () => {
    const v = validateConnect({ token: ` ${TOKEN} `, account: "act_123456", page: "" });
    expect(v.ok).toBe(true);
    if (!v.ok) return;
    const args = connectArgs(v.value);
    expect(args).toEqual(["run", "whynot", "connect", "--token-stdin", "--json", "--account=123456"]);
    expect(args.join(" ")).not.toContain(TOKEN);
  });

  it.each([[{ token: "short" }], [{ token: `${TOKEN}; rm -rf /` }], [{ token: TOKEN, account: "--live" }], [null]])("refuses %j", (input) => {
    expect(validateConnect(input).ok).toBe(false);
  });

  it("sends the token on stdin and returns the saved connection without it", async () => {
    const dir = process.env.WHYNOT_CONNECTIONS_DIR!;
    const engine = fakeEngine(`mkdir -p "${dir}"; printf '%s' '${JSON.stringify({ token: TOKEN, account_id: "123456", account_name: "Shop", currency: "EUR", page_id: "9", page_name: "P", granted: ["ads_management"] })}' > "${dir}/act_123456.json"
echo '{"ok": true, "account_id": "123456"}'`);
    const res = await runConnect({ token: TOKEN }, { command: engine });
    expect(res).toMatchObject({ ok: true, connection: { act: "act_123456", accountName: "Shop", canPublish: true } });
    expect(JSON.stringify(res)).not.toContain(TOKEN);
    expect(fs.readFileSync(path.join(root, "stdin.txt"), "utf8").trim()).toBe(TOKEN);
    expect(fs.readFileSync(path.join(root, "args.txt"), "utf8")).not.toContain(TOKEN);
  });

  it("reports Meta's refusal without echoing the token", async () => {
    const engine = fakeEngine(`echo '{"ok": false, "error": "login ${TOKEN} expired, see https://x?access_token=${TOKEN}"}'; exit 1`);
    const res = await runConnect({ token: TOKEN }, { command: engine });
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.error).toBe("login [token] expired, see https://x?access_token=[token]");
  });

  it("an engine that cannot start is reported, not thrown", async () => {
    const res = await runConnect({ token: TOKEN }, { command: "/nope/uv" });
    expect(res.ok).toBe(false);
  });

  it("scrubs tokens in URLs too", () => {
    expect(scrub("https://g.com/x?a=1&access_token=OTHER&b=2", TOKEN)).toBe("https://g.com/x?a=1&access_token=[token]&b=2");
  });
});

describe("starting the agency", () => {
  const conn = (over: Partial<Connection> = {}): Connection => ({
    act: "act_123456", accountId: "123456", accountName: "Shop", currency: "EUR", pageId: "9", pageName: "P", appId: null,
    userName: "O", sandbox: false, warnings: [], connectedAt: null, expiresAt: null, daysLeft: 30, canPublish: true, ...over,
  });
  const ok = { app: APP, countries: "us gb", dailyCapEur: 20, account: "123456", level: "autopilot", paused: true };

  it("on a connected account: the engine gets the connection file, the level, paused and the folder", () => {
    const v = validateAgency(ok, [conn()]);
    expect(v.ok).toBe(true);
    if (!v.ok) return;
    expect(v.value).toMatchObject({ countries: ["US", "GB"], account: "123456", level: "autopilot", paused: true, budgetUsd: 8 });
    expect(agencyArgs(v.value, "/runs/web/x", "/c/act_123456.json")).toEqual(["run", "whynot", "agency", APP, "--countries", "US", "GB",
      "--daily-cap=20", "--budget-usd=8", "--connection=/c/act_123456.json", "--level=autopilot", "--paused", "--run-dir=/runs/web/x", "--json"]);
  });

  it("without an account: the simulated account, and an unknown level falls back to dry run", () => {
    const v = validateAgency({ ...ok, account: undefined, level: "yolo" }, []);
    expect(v.ok).toBe(true);
    if (v.ok) expect(agencyArgs(v.value, "/r", null)).toEqual(expect.arrayContaining(["--sim", "--level=dry_run"]));
  });

  it.each([
    [{ ...ok, app: "https://evil.example/app" }, "app store"], [{ ...ok, app: "--live" }, "app store"],
    [{ ...ok, countries: "USA" }, "countries"], [{ ...ok, dailyCapEur: 1 }, "budget"], [{ ...ok, dailyCapEur: "1e9" }, "budget"],
    [{ ...ok, account: "999" }, "connect"], [{ ...ok, landingUrl: "http://x.com" }, "https"],
  ])("refuses %j", (input, error) => {
    const v = validateAgency(input, [conn()]);
    expect(v.ok).toBe(false);
    if (!v.ok) expect(v.error.toLowerCase()).toContain(error);
  });

  it("refuses an expired login or one that cannot publish", () => {
    expect(validateAgency(ok, [conn({ daysLeft: -1 })]).ok).toBe(false);
    expect(validateAgency(ok, [conn({ canPublish: false })]).ok).toBe(false);
  });

  it("starts in the background and the page can open at once", async () => {
    const file = saveConnection({ account_id: "123456" });
    const engine = fakeEngine(`echo '{"ok": true, "status": "waiting"}'`);
    const v = validateAgency(ok);
    expect(v.ok).toBe(true);
    if (!v.ok) return;
    const id = startAgency(v.value, { command: engine });
    expect(id.startsWith("web/")).toBe(true);
    expect(readRun(id).config?.app_ref).toBe(APP);
    const args = await argsWritten();
    expect(args).toContain(`--connection=${file}`);
    expect(args).toContain(`--run-dir=${path.join(process.env.WHYNOT_RUNS_DIR!, id)}`);
    expect(fs.readFileSync(path.join(process.env.WHYNOT_RUNS_DIR!, id, "agency", "site.log"), "utf8")).toContain("act_123456 autopilot paused");
  });
});

describe("the owner's buttons", () => {
  it("approve: the name is one argument and cannot be an option", () => {
    expect(validateResume({ id: "web/x", approvedBy: "--live" }).ok).toBe(false);
    const v = validateResume({ id: "web/x", approvedBy: "Matteo" });
    expect(v.ok && resumeArgs(v.value, "/r")).toEqual(["run", "whynot", "agency", "--resume=/r", "--approve=Matteo", "--json"]);
    const plain = validateResume({ id: "web/x" });
    expect(plain.ok && resumeArgs(plain.value, "/r")).toEqual(["run", "whynot", "agency", "--resume=/r", "--json"]);
  });

  it("resume only for agency runs inside the runs folder", async () => {
    const engine = fakeEngine("true");
    expect(() => resumeAgency({ id: "../../etc", approvedBy: null }, { command: engine })).toThrow(RunPathError);
    const plain = path.join(process.env.WHYNOT_RUNS_DIR!, "web", "plain");
    fs.mkdirSync(plain, { recursive: true });
    fs.writeFileSync(path.join(plain, "config.json"), "{}");
    expect(() => resumeAgency({ id: "web/plain", approvedBy: null }, { command: engine })).toThrow("not an agency run");
    const dir = agencyRun({ steps: {}, days: {}, config: {} });
    resumeAgency({ id: "web/x", approvedBy: "Matteo" }, { command: engine });
    expect(await argsWritten()).toContain(`--resume=${dir}`);
  });

  it("schedule: a time or remove, nothing else", async () => {
    expect(validateSchedule({ id: "web/x", at: "8am" }).ok).toBe(false);
    expect(validateSchedule({ id: "web/x", at: "24:00" }).ok).toBe(false);
    const v = validateSchedule({ id: "web/x", at: "08:30" });
    expect(v.ok && scheduleArgs(v.value, "/r")).toEqual(["run", "whynot", "schedule", "/r", "--at=08:30", "--json"]);
    const off = validateSchedule({ id: "web/x", remove: true });
    expect(off.ok && scheduleArgs(off.value, "/r")).toEqual(["run", "whynot", "schedule", "/r", "--remove", "--json"]);
    agencyRun({ steps: {}, days: {}, config: {} });
    expect(await runSchedule({ id: "web/x", at: "08:30" }, { command: fakeEngine("echo '{}'") })).toEqual({ ok: true });
    expect(await runSchedule({ id: "web/x", at: "08:30" }, { command: fakeEngine("echo '✗ launchctl failed' >&2; exit 1") }))
      .toEqual({ ok: false, error: "launchctl failed" });
  });

  it("kill switch: on the account the agency used, with its connection", async () => {
    expect(validateAgencyStop({ id: "web/x", by: "--live" }).ok).toBe(false);
    const file = saveConnection();
    const dir = agencyRun({ steps: {}, days: {}, config: {}, account: { account_id: "2579757785851312", granted: ["ads_management"], page_id: "1" } });
    const res = await runAgencyStop({ id: "web/x", by: "Matteo" }, { command: fakeEngine("echo '✓ LIVE act_2579757785851312: 3 paused'") });
    expect(res.ok).toBe(true);
    const args = fs.readFileSync(path.join(root, "args.txt"), "utf8").split("\n");
    expect(args).toEqual(expect.arrayContaining(["stop", dir, "--by=Matteo", `--connection=${file}`]));
    expect(fs.readFileSync(path.join(dir, "stop.log"), "utf8")).toContain("agency stop by Matteo");
  });

  it("kill switch on a simulated run: nothing to stop on Meta", async () => {
    agencyRun({ steps: {}, days: {}, config: { simulated_account: true } });
    const res = await runAgencyStop({ id: "web/x", by: "Matteo" }, { command: fakeEngine("true") });
    expect(res.ok).toBe(false);
    expect(res.lines[0]).toContain("no Meta connection");
  });
});

describe("the run page", () => {
  it("reads the agency's state: account without token, steps, days newest first, waiting", () => {
    const dir = agencyRun({
      config: { level: "autopilot", paused_only: true, daily_cap_eur: 20 }, objective: "traffic", website: "https://www.vietbuddy.app/",
      account: { account_id: "2579757785851312", account_name: "Owner", page_id: "1", page_name: "Whynot test", granted: ["ads_management"], token: TOKEN },
      steps: { connect: { status: "ok", outputs: { objective: "traffic" } }, create: { status: "ok", usd: 1.2, outputs: {} },
        publish: { status: "waiting", error: "first live launch needs your approval", outputs: {} } },
      days: { "2026-11-01": { status: "ok", outputs: { new: 1 } }, "2026-11-02": { status: "ok", outputs: { new: 2 } } },
      schedule: { at: "08:00", how: "launchd", installed: true },
    });
    const a = readAgency(dir)!;
    expect(a).toMatchObject({ simulated: false, level: "autopilot", paused: true, objective: "traffic", waiting: true,
      schedule: { at: "08:00", installed: true } });
    expect(a.account?.pageName).toBe("Whynot test");
    expect(a.steps.publish?.status).toBe("waiting");
    expect(a.days.map((d) => d.day)).toEqual(["2026-11-02", "2026-11-01"]);
    expect(JSON.stringify(a)).not.toContain(TOKEN);
    expect(readRun("web/x").agency?.waiting).toBe(true);
  });

  it("is running while the engine writes and its log has no final line; then not", () => {
    const dir = agencyRun({ steps: {}, days: {}, config: {} });
    fs.writeFileSync(path.join(dir, "agency", "site.log"), "\n--- 2026 start\nconnect…\n");
    expect(readAgency(dir)?.running).toBe(true);
    fs.appendFileSync(path.join(dir, "agency", "site.log"), '{"ok": true, "status": "done"}\n');
    expect(readAgency(dir)?.running).toBe(false);
  });

  it("a run made with `whynot create` only has no agency", () => {
    const dir = path.join(process.env.WHYNOT_RUNS_DIR!, "web", "plain");
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, "config.json"), "{}");
    expect(readAgency(dir)).toBeNull();
  });
});
