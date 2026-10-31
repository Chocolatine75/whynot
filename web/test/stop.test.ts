import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { RunPathError } from "@/lib/runs";
import { missingForStop, runStop, stopArgs, validateStop } from "@/lib/stop";

describe("kill switch requests", () => {
  const ok = { id: "web/x", mode: "live", by: "Tom Angles" };

  it("accepts a named request and builds an argument list (no shell)", () => {
    const v = validateStop(ok);
    expect(v.ok).toBe(true);
    if (!v.ok) return;
    expect(stopArgs(v.value, "/runs/web/x")).toEqual(["run", "whynot", "stop", "/runs/web/x", "--by=Tom Angles", "--live"]);
    expect(stopArgs({ ...v.value, mode: "sandbox" }, "/r")).toEqual(["run", "whynot", "stop", "/r", "--by=Tom Angles"]);
  });

  it.each([
    [{ ...ok, by: "--live" }, "name"], [{ ...ok, by: "" }, "name"], [{ ...ok, by: "Tom; rm -rf /" }, "name"],
    [{ ...ok, mode: "prod" }, "sandbox or live"], [{ ...ok, id: "" }, "campaign"], [null, "campaign"],
  ])("refuses %j", (input, error) => {
    const v = validateStop(input);
    expect(v.ok).toBe(false);
    if (!v.ok) expect(v.error.toLowerCase()).toContain(error);
  });

  it("names the settings it needs for each account", () => {
    expect(missingForStop("sandbox", new Set(["META_SANDBOX_TOKEN"]))).toEqual(["META_SANDBOX_AD_ACCOUNT_ID"]);
    expect(missingForStop("live", new Set(["META_AD_ACCOUNT_ID", "META_ACCESS_TOKEN"]))).toEqual([]);
  });
});

describe("running the kill switch", () => {
  const saved = process.env.WHYNOT_RUNS_DIR;
  afterEach(() => { process.env.WHYNOT_RUNS_DIR = saved; });

  function setup(exitCode: number): { command: string; run: string } {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "stop-"));
    const run = path.join(root, "runs", "web", "x");
    fs.mkdirSync(run, { recursive: true });
    fs.writeFileSync(path.join(run, "config.json"), "{}");
    const command = path.join(root, "fake-uv.sh");  // a stand-in engine that echoes what it was given
    fs.writeFileSync(command, `#!/bin/sh\nfor a in "$@"; do echo "arg: $a"; done\necho "done" >&2\nexit ${exitCode}\n`);
    fs.chmodSync(command, 0o755);
    process.env.WHYNOT_RUNS_DIR = path.join(root, "runs");
    return { command, run };
  }

  it("passes the name as one argument, reports the output and logs it", async () => {
    const { command, run } = setup(0);
    const result = await runStop({ id: "web/x", mode: "sandbox", by: "Tom Angles" }, { command });
    expect(result.ok).toBe(true);
    expect(result.lines).toContain("arg: --by=Tom Angles");
    expect(result.lines).not.toContain("arg: --live");
    expect(fs.readFileSync(path.join(run, "stop.log"), "utf8")).toContain("sandbox by Tom Angles");
  });

  it("a failing engine is reported as not ok", async () => {
    const { command } = setup(2);
    expect((await runStop({ id: "web/x", mode: "live", by: "Tom" }, { command })).ok).toBe(false);
  });

  it("an engine that cannot start is reported, not thrown", async () => {
    setup(0);
    const result = await runStop({ id: "web/x", mode: "live", by: "Tom" }, { command: "/nope/uv" });
    expect(result.ok).toBe(false);
    expect(result.lines.join(" ")).toContain("could not start");
    await new Promise((r) => setTimeout(r, 50));  // let a late "close" event arrive: still one log entry
    const log = fs.readFileSync(path.join(process.env.WHYNOT_RUNS_DIR!, "web", "x", "stop.log"), "utf8");
    expect(log.match(/^--- /gm)?.length).toBe(1);
  });

  it("unknown runs never reach the engine", () => {
    const { command } = setup(0);
    expect(() => runStop({ id: "../../etc", mode: "live", by: "Tom" }, { command })).toThrow(RunPathError);
    expect(() => runStop({ id: "web/missing", mode: "live", by: "Tom" }, { command })).toThrow(RunPathError);
  });
});
