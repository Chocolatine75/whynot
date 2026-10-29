import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { RunPathError, listRuns, readRun, resolveRun, resolveRunFile, runStatus, stageStates, totalSpent, type RunEvent } from "@/lib/runs";

let root: string;

function makeRun(id: string, events: Partial<RunEvent>[], files: Record<string, unknown> = {}) {
  const dir = path.join(root, id);
  fs.mkdirSync(path.join(dir, "ads"), { recursive: true });
  fs.writeFileSync(path.join(dir, "config.json"), JSON.stringify({ app_ref: "x", countries: ["US"], daily_cap_eur: 20, budget_usd: 3 }));
  fs.writeFileSync(path.join(dir, "events.jsonl"), events.map((e) => JSON.stringify({ ts: "2026-10-29T10:00:00Z", ...e })).join("\n") + "\n");
  for (const [name, data] of Object.entries(files)) fs.writeFileSync(path.join(dir, name), typeof data === "string" ? data : JSON.stringify(data));
  return dir;
}

beforeEach(() => {
  root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "whynot-runs-")));
});

describe("paths are confined to the runs folder", () => {
  it("resolves a run and its files", () => {
    makeRun("a", [], { "ads/x.png": "png" });
    expect(resolveRun("a", root)).toBe(path.join(root, "a"));
    expect(resolveRunFile("a", "ads/x.png", root).type).toBe("image/png");
  });

  it.each(["../a", "/etc", "a/../../etc", "", "a\0b", "missing"])("refuses run id %j", (id) => {
    makeRun("a", []);
    expect(() => resolveRun(id, root)).toThrow(RunPathError);
  });

  it.each(["../../etc/passwd", "/etc/passwd", "config.json", "events.jsonl", "ads/../../a/config.json", "ads/nope.png", "assets/"])(
    "refuses file %j", (rel) => {
      makeRun("a", [], { "ads/x.png": "png" });
      expect(() => resolveRunFile("a", rel, root)).toThrow(RunPathError);
    });

  it("refuses a symlink inside the run that points outside it", () => {
    const dir = makeRun("a", []);
    const outside = fs.mkdtempSync(path.join(os.tmpdir(), "outside-"));
    fs.writeFileSync(path.join(outside, "secret.png"), "secret");
    fs.symlinkSync(outside, path.join(dir, "link"));
    fs.symlinkSync(path.join(outside, "secret.png"), path.join(dir, "ads", "evil.png"));
    expect(() => resolveRunFile("a", "link/secret.png", root)).toThrow(RunPathError);
    expect(() => resolveRunFile("a", "ads/evil.png", root)).toThrow(RunPathError);
  });

  it("refuses a run folder that is a symlink to elsewhere", () => {
    const outside = fs.mkdtempSync(path.join(os.tmpdir(), "outside-run-"));
    fs.writeFileSync(path.join(outside, "config.json"), "{}");
    fs.symlinkSync(outside, path.join(root, "linked"));
    expect(() => resolveRun("linked", root)).toThrow(RunPathError);
  });
});

describe("stage states come from the event log", () => {
  it("tracks start, ok, error and spend", () => {
    const s = stageStates([
      { ts: "", stage: "app", status: "start" }, { ts: "", stage: "app", status: "ok", usd: 0 },
      { ts: "", stage: "market", status: "start" }, { ts: "", stage: "market", status: "ok", usd: 0.02 },
      { ts: "", stage: "strategy", status: "start" }, { ts: "", stage: "strategy", status: "error", usd: 0.5, error: "boom" },
    ] as RunEvent[]);
    expect(s.map((x) => x.state).slice(0, 4)).toEqual(["done", "done", "error", "pending"]);
    expect(s[2].error).toBe("boom");
    expect(s[1].usd).toBeCloseTo(0.02);
  });

  it("a redo resets the stage and every later one, but spend stays counted", () => {
    const events = [
      ...["app", "market", "strategy", "creative"].flatMap((stage) => [{ ts: "", stage, status: "start" }, { ts: "", stage, status: "ok", usd: 0.1 }]),
      { ts: "", stage: "strategy", status: "redo" },
      { ts: "", stage: "app", status: "cached" }, { ts: "", stage: "market", status: "cached" }, { ts: "", stage: "strategy", status: "start" },
    ] as RunEvent[];
    const s = stageStates(events);
    expect(s.map((x) => x.state).slice(0, 4)).toEqual(["cached", "cached", "running", "pending"]);
    expect(totalSpent(events)).toBeCloseTo(0.4);
  });

  it("status: done, failed, running, or stopped when the process went quiet", () => {
    const now = Date.parse("2026-10-29T10:05:00Z");
    const running = stageStates([{ ts: "", stage: "app", status: "start" }] as RunEvent[]);
    expect(runStatus(running, Date.parse("2026-10-29T10:04:00Z"), now)).toBe("running");
    expect(runStatus(running, Date.parse("2026-10-29T09:00:00Z"), now)).toBe("stopped");
    const failed = stageStates([{ ts: "", stage: "app", status: "error" }] as RunEvent[]);
    expect(runStatus(failed, now, now)).toBe("failed");
    const all = stageStates(["app", "market", "strategy", "creative", "produce", "simulate", "evolve", "plan", "report"]
      .map((stage) => ({ ts: "", stage, status: "ok" })) as RunEvent[]);
    expect(runStatus(all, now, now)).toBe("done");
  });
});

it("a finished run made before a stage existed counts as done, the missing stage as skipped", () => {
  const events = ["app", "market", "strategy", "creative", "produce", "simulate", "plan", "report"]
    .map((stage) => ({ ts: "", stage, status: "ok" })) as RunEvent[];
  const s = stageStates(events);
  expect(s.find((x) => x.stage === "evolve")?.state).toBe("skipped");
  expect(runStatus(s, 0, Date.now())).toBe("done");
});

describe("reading runs", () => {
  it("reads a run, tolerates half-written files, lists nested runs newest first", () => {
    makeRun("old", [{ stage: "app", status: "start", ts: "2026-10-28T10:00:00Z" }], { "app.json": { name: "Old app" } });
    makeRun("web/new", [{ stage: "app", status: "start", ts: "2026-10-29T10:00:00Z" }], { "strategy.json": "{ half written" });
    const r = readRun("web/new", root);
    expect(r.strategy).toBeNull();
    expect(r.variants).toEqual([]);
    const list = listRuns(root);
    expect(list.map((x) => x.id)).toEqual(["web/new", "old"]);
    expect(list[1].appName).toBe("Old app");
  });

  it("an empty or missing root lists nothing", () => {
    expect(listRuns(path.join(root, "nope"))).toEqual([]);
  });
});
